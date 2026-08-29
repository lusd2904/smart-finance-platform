"""资金看板解析：板块 / 涨停 / 龙虎榜 / Nasdaq 日历。"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.flow_board_service import (
    _cn_trade_date_candidates,
    parse_lhb_payload,
    parse_limit_up_payload,
    parse_nasdaq_earnings,
    parse_nasdaq_events,
    parse_sector_payload,
)


def test_parse_sector_from_eastmoney_diff() -> None:
    payload = {
        'data': {
            'diff': [
                {
                    'f12': 'BK1206',
                    'f14': '基础化工',
                    'f2': 3717.34,
                    'f3': 1.57,
                    'f62': 2678371072.0,
                    'f184': 1.93,
                    'f204': '红 宝 丽',
                    'f205': '002165',
                }
            ]
        }
    }
    items = parse_sector_payload(payload)
    assert items[0]['code'] == 'BK1206'
    assert items[0]['name'] == '基础化工'
    assert items[0]['netInflow'] == 2678371072.0
    assert items[0]['leaderName'] == '红宝丽'


def test_parse_sector_object_diff() -> None:
    payload = {'data': {'diff': {'0': {'f12': 'BK0001', 'f14': '半导体', 'f62': 1}}}}
    items = parse_sector_payload(payload)
    assert len(items) == 1
    assert items[0]['name'] == '半导体'


def test_parse_limit_up_price_scaled() -> None:
    payload = {
        'data': {
            'tc': 82,
            'pool': [{'c': '000712', 'n': '锦龙股份', 'p': 11800, 'zdp': 9.97, 'lbc': 3, 'hybk': '证券Ⅱ'}],
        }
    }
    items = parse_limit_up_payload(payload)
    assert items[0]['symbol'] == '000712'
    assert items[0]['last'] == 11.8
    assert items[0]['boards'] == 3


def test_parse_lhb_and_calendars() -> None:
    lhb = {
        'result': {
            'data': [
                {
                    'SECURITY_CODE': '001232',
                    'SECURITY_NAME_ABBR': '嘉立创',
                    'TRADE_DATE': '2026-08-28 00:00:00',
                    'CLOSE_PRICE': 175.01,
                    'CHANGE_RATE': 8.01,
                    'BILLBOARD_NET_AMT': 652436808.6,
                    'EXPLAIN': '3家机构买入',
                }
            ]
        }
    }
    rows = parse_lhb_payload(lhb)
    assert rows[0]['symbol'] == '001232'
    assert rows[0]['tradeDate'] == '2026-08-28'

    events = parse_nasdaq_events(
        {'data': {'asOf': 'Sat, Aug 29, 2026', 'rows': [{'gmt': '02:00', 'country': 'Germany', 'eventName': 'CPI'}]}}
    )
    assert events[0]['kind'] == 'macro'
    assert events[0]['title'] == 'CPI'

    earns = parse_nasdaq_earnings({'data': {'rows': [{'symbol': 'aapl', 'name': 'Apple', 'epsForecast': '1.2'}]}})
    assert earns[0]['symbol'] == 'AAPL'


def test_cn_trade_date_skips_weekend() -> None:
    saturday = datetime(2026, 8, 29, 12, 0, tzinfo=ZoneInfo('Asia/Shanghai'))
    dates = _cn_trade_date_candidates(saturday)
    assert dates[0] == '2026-08-28'
    assert all(datetime.strptime(d, '%Y-%m-%d').weekday() < 5 for d in dates)
