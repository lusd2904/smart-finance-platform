import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_ai.service.ai_req_service import AiReqService, extract_requirement_payload, system_prompt
from module_trade.service.feishu_push_service import DISCLAIMER, build_card, due_now
from utils.job_queue import JobQueue, group_for
from utils.trading_calendar import is_cn_trading_day, is_market_session_open, next_cn_trading_day


def test_default_round_prompt_hides_peers_on_round_one() -> None:
    text = system_prompt(name='Grok', is_decider=False, round_no=1, peer_notes='- 别人: 可行', write_allowed=False)
    assert '独立判断' in text
    assert '禁止输出' in text


def test_later_round_must_comment_peers() -> None:
    text = system_prompt(name='Claude', is_decider=False, round_no=2, peer_notes='- Grok: 风险高', write_allowed=False)
    assert '点评其他 AI' in text
    assert '风险高' in text


def test_only_decider_may_write_when_confirmed() -> None:
    allowed = system_prompt(name='Grok', is_decider=True, round_no=2, peer_notes='', write_allowed=True)
    denied = system_prompt(name='Grok', is_decider=True, round_no=2, peer_notes='', write_allowed=False)
    other = system_prompt(name='Other', is_decider=False, round_no=2, peer_notes='', write_allowed=True)
    assert 'upsert_requirements' in allowed
    assert '尚未确认' in denied
    assert '不是确定者' in other


def test_save_bots_rejects_duplicate_model() -> None:
    import asyncio
    from unittest.mock import MagicMock

    from exceptions.exception import ServiceException

    async def _run() -> None:
        with pytest.raises(ServiceException) as err:
            await AiReqService.save_bots_services(
                MagicMock(),
                {
                    'bots': [
                        {'modelId': 1, 'displayName': 'A', 'enabled': True, 'isDecider': True},
                        {'modelId': 1, 'displayName': 'B', 'enabled': True, 'isDecider': False},
                    ]
                },
            )
        assert '重复' in (err.value.message or '')

    asyncio.run(_run())


def test_confirm_text() -> None:
    assert AiReqService.is_confirm_text('确定需求，写入清单')
    assert AiReqService.is_confirm_text('请总结已确定的需求并写入需求清单。')
    assert AiReqService.is_confirm_text('确定')
    assert AiReqService.is_confirm_text('确认')
    assert not AiReqService.is_confirm_text('先看看风险')


def test_infer_round_caps_at_three() -> None:
    history = [
        {'role': 'user', 'content': 'a'},
        {'role': 'ai', 'content': '1'},
        {'role': 'user', 'content': 'b'},
        {'role': 'ai', 'content': '2'},
        {'role': 'ai', 'content': '2b'},
        {'role': 'user', 'content': 'c'},
        {'role': 'ai', 'content': '3'},
    ]
    assert AiReqService.infer_round(history) == 3


def test_extract_still_parses_action() -> None:
    items = extract_requirement_payload(
        '结论。{"action":"upsert_requirements","items":[{"title":"飞书推送","detail":"卡片","priority":"P0"}]}'
    )
    assert items[0]['title'] == '飞书推送'


def test_cn_weekend_and_holiday() -> None:
    assert is_cn_trading_day(date(2026, 8, 21)) is True  # Friday
    assert is_cn_trading_day(date(2026, 8, 22)) is False  # Saturday
    assert is_cn_trading_day(date(2026, 10, 1)) is False
    nxt = next_cn_trading_day(date(2026, 10, 1))
    assert nxt > date(2026, 10, 8)


def test_session_closed_on_weekend() -> None:
    saturday = datetime(2026, 8, 22, 10, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert is_market_session_open('CN', saturday) is False


def test_us_session_open_pre_post_overnight() -> None:
    et = ZoneInfo('America/New_York')
    assert is_market_session_open('US', datetime(2026, 8, 25, 8, 0, tzinfo=et)) is True
    assert is_market_session_open('US', datetime(2026, 8, 25, 17, 0, tzinfo=et)) is True
    assert is_market_session_open('US', datetime(2026, 8, 25, 21, 0, tzinfo=et)) is True
    assert is_market_session_open('US', datetime(2026, 8, 23, 21, 0, tzinfo=et)) is True
    assert is_market_session_open('US', datetime(2026, 8, 23, 12, 0, tzinfo=et)) is False
    assert is_market_session_open('US', datetime(2026, 8, 29, 12, 0, tzinfo=et)) is False


def test_feishu_card_has_disclaimer_and_not_advice() -> None:
    card = build_card(
        {
            'tradeDate': '2026-08-24',
            'itemCount': 1,
            'items': [{'symbol': 'AAPL', 'market': 'US', 'signal': 'BUY', 'score': 70, 'reason': '趋势向上'}],
        }
    )
    blob = str(card)
    assert DISCLAIMER in blob
    assert '荐股' in DISCLAIMER
    assert 'AAPL' in blob


def test_feishu_due_window() -> None:
    now = datetime(2026, 8, 21, 18, 32, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert due_now('18:30', 'Asia/Shanghai', now) is True
    assert due_now('19:00', 'Asia/Shanghai', now) is False


def test_new_jobs_are_queued() -> None:
    assert group_for('daily_list_scan') == 'quant'
    assert group_for('daily_list_open') == 'quant'
    assert group_for('feishu_push') == 'llm'
    raw = JobQueue.encode('daily_list_scan', {'userId': 101})
    job = JobQueue.decode(raw)
    assert job['type'] == 'daily_list_scan'
