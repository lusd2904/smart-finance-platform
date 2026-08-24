import os
import sys
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.stock_pick_scoring import (
    apply_ai_result,
    combine_pick_score,
    is_index_symbol,
    merge_candidates,
    normalize_sentiment,
    reco_from_signal,
    select_top_picks,
)
from module_market.service.stock_pick_service import StockPickService
from module_market.service.sync_service import eod_session_date, should_skip_eod


def test_closed_market_drops_index_from_score() -> None:
    closed = combine_pick_score(80, sentiment_raw=2, heat_score=90, index_open=False, index_change_pct=3)
    opened = combine_pick_score(80, sentiment_raw=2, heat_score=90, index_open=True, index_change_pct=3)
    assert closed != opened
    only_factor_sent = combine_pick_score(80, sentiment_raw=2, heat_score=10, index_open=False, index_change_pct=-8)
    assert closed == only_factor_sent


def test_normalize_and_reco() -> None:
    assert normalize_sentiment(0) == 50
    assert normalize_sentiment(10) == 100
    assert reco_from_signal('BUY', 70) == ('买入', '偏多')
    assert reco_from_signal('SELL', 40) == ('回避', '偏空')
    assert is_index_symbol('^GSPC', 'index') is True
    assert is_index_symbol('AAPL', 'mag7') is False


def test_merge_and_select() -> None:
    top = [{'symbol': 'AAPL', 'name': '苹果', 'market': 'US'}]
    feat = [
        {'symbol': 'AAPL', 'name': '苹果', 'market': 'US', 'category': 'mag7'},
        {'symbol': '^DJI', 'name': '道指', 'market': 'US', 'category': 'index'},
        {'symbol': '600519', 'name': '茅台', 'market': 'CN', 'category': 'star'},
    ]
    merged = merge_candidates(top, feat, cap=10)
    assert [r['symbol'] for r in merged] == ['AAPL', '600519']
    rows = [
        {'symbol': 'A', 'market': 'US', 'signal': 'HOLD', 'pickScore': 90},
        {'symbol': 'B', 'market': 'US', 'signal': 'BUY', 'pickScore': 60},
        {'symbol': 'C', 'market': 'CN', 'signal': 'BUY', 'pickScore': 70},
    ]
    picked = select_top_picks(rows, per_market=1)
    us = [r for r in picked if r['market'] == 'US']
    assert us[0]['symbol'] == 'B'


def test_apply_ai_result_overwrites_rule_advice() -> None:
    row = {
        'source': 'rule',
        'recommendation': '观望',
        'stance': '中性',
        'summary': '规则摘要',
        'confidence': 50,
    }
    apply_ai_result(
        row,
        {
            'stance': '偏多',
            'recommendation': '买入',
            'confidence': 78,
            'summary': 'AI 认为趋势延续',
            'indicator_review': '站上均线',
            'sentiment_review': '舆情偏多',
            'operation_advice': '回踩加仓',
            'risk_warning': '注意放量',
        },
    )
    assert row['source'] == 'ai'
    assert row['recommendation'] == '买入'
    assert row['summary'] == 'AI 认为趋势延续'
    assert row['operationAdvice'] == '回踩加仓'
    assert row['confidence'] == 78


def test_eod_skip_and_session_date() -> None:
    assert should_skip_eod(None, date(2026, 8, 21)) is False
    assert should_skip_eod('2026-08-21', date(2026, 8, 21)) is True
    assert should_skip_eod('2026-08-20', date(2026, 8, 21)) is False
    cn_close = datetime(2026, 8, 21, 15, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert eod_session_date('CN', cn_close) == date(2026, 8, 21)
    us_after = datetime(2026, 8, 19, 5, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert eod_session_date('US', us_after) == date(2026, 8, 18)


def test_list_dates_services_serializes_rows() -> None:
    rows = [
        SimpleNamespace(
            pick_id=2,
            trade_date='2026-08-21',
            status='ok',
            picked_count=15,
            ai_count=15,
            model_name='grok-4.6',
            update_time=datetime(2026, 8, 21, 18, 0, 0),
        ),
        SimpleNamespace(
            pick_id=1,
            trade_date='2026-08-20',
            status='partial',
            picked_count=15,
            ai_count=10,
            model_name='grok-4.6',
            update_time=datetime(2026, 8, 20, 18, 0, 0),
        ),
    ]

    async def _run() -> None:
        with patch('module_market.service.stock_pick_service.StockPickDao.list_dates', new=AsyncMock(return_value=rows)):
            data = await StockPickService.list_dates_services(None, limit=60)
        assert len(data['dates']) == 2
        assert data['dates'][0]['tradeDate'] == '2026-08-21'
        assert data['dates'][0]['pickedCount'] == 15
        assert data['dates'][1]['updatedAt'] == '2026-08-20 18:00:00'

    import asyncio

    asyncio.run(_run())


def test_get_latest_services_missing_date_returns_empty_message() -> None:
    async def _run() -> None:
        with (
            patch('module_market.service.stock_pick_service.StockPickDao.get_by_date', new=AsyncMock(return_value=None)),
            patch(
                'module_market.service.stock_pick_service.StockPickService.get_mood_services',
                new=AsyncMock(return_value={'hint': 'ok'}),
            ),
        ):
            data = await StockPickService.get_latest_services(None, trade_date='2026-08-01')
        assert data['empty'] is True
        assert data['tradeDate'] == '2026-08-01'
        assert data['message'] == '该交易日暂无选股单'
        assert data['items'] == []

    import asyncio

    asyncio.run(_run())


def test_analyze_symbol_scores_and_applies_ai() -> None:
    klines = [
        {'date': f'2026-01-{d:02d}', 'open': 100 + d, 'high': 101 + d, 'low': 99 + d, 'close': 100 + d, 'volume': 1e6}
        for d in range(1, 61)
    ]
    mood = {
        'openMarkets': ['US'],
        'sentiment': {'summary': '舆情偏多', 'usScore': 3},
        'heat': {'US': {'heatScore': 72, 'tradeDate': '2026-08-21'}},
        'indices': [{'market': 'US', 'changePct': 1.2}],
    }
    ai_payload = {
        'stance': '偏多',
        'recommendation': '买入',
        'confidence': 81,
        'summary': 'AI 综合研判',
        'indicator_review': '均线多头',
        'sentiment_review': '舆情支持',
        'operation_advice': '回踩关注',
        'risk_warning': '注意波动',
    }

    async def _run() -> None:
        with (
            patch(
                'module_market.service.stock_pick_service.StockPickDao.load_recent_daily_klines',
                new=AsyncMock(return_value={'AAPL': klines}),
            ),
            patch(
                'module_market.service.stock_pick_service.StockPickService.get_mood_services',
                new=AsyncMock(return_value=mood),
            ),
            patch(
                'module_market.service.stock_pick_service.StockPickService._resolve_ai',
                new=AsyncMock(
                    return_value={
                        'available': True,
                        'baseUrl': 'https://example.com/v1',
                        'apiKey': 'k',
                        'modelName': 'grok-4.6',
                        'temperature': 0.2,
                    }
                ),
            ),
            patch(
                'module_market.service.stock_pick_service.StockPickAnalyzer.analyze',
                new=AsyncMock(return_value={'ok': True, 'result': ai_payload}),
            ),
        ):
            data = await StockPickService.analyze_symbol(None, 'AAPL', 'US', use_ai=True)
        assert data['ok'] is True
        assert data['symbol'] == 'AAPL'
        assert data['recommendation'] == '买入'
        assert data['stance'] == '偏多'
        assert data['confidence'] == 81
        assert data['summary'] == 'AI 综合研判'
        assert data['indicatorReview'] == '均线多头'
        assert data['sentimentReview'] == '舆情支持'
        assert data['operationAdvice'] == '回踩关注'
        assert data['riskWarning'] == '注意波动'
        assert data['source'] == 'ai'
        assert data['modelName'] == 'grok-4.6'
        assert data['pickScore'] is not None
        assert data['factorScore'] is not None

    import asyncio

    asyncio.run(_run())


def test_analyze_symbol_without_klines_returns_error() -> None:
    async def _run() -> None:
        with patch(
            'module_market.service.stock_pick_service.StockPickDao.load_recent_daily_klines',
            new=AsyncMock(return_value={}),
        ):
            data = await StockPickService.analyze_symbol(None, 'AAPL', 'US')
        assert data['ok'] is False
        assert '暂无K线' in str(data.get('message'))

    import asyncio

    asyncio.run(_run())
