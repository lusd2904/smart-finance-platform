import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.time_format_util import (
    BEIJING_TZ,
    apply_beijing_times,
    encode_api_datetime,
    format_beijing_datetime,
    format_utc_as_beijing,
    now_beijing,
)


def test_aware_utc_converts_to_beijing() -> None:
    utc = datetime(2026, 8, 24, 4, 55, 0, tzinfo=timezone.utc)
    assert format_beijing_datetime(utc) == '2026-08-24 12:55:00'


def test_naive_keeps_wall_clock() -> None:
    naive = datetime(2026, 8, 24, 20, 0, 0)
    assert format_beijing_datetime(naive) == '2026-08-24 20:00:00'


def test_iso_z_string_converts_to_beijing() -> None:
    assert format_beijing_datetime('2026-08-24T04:55:00Z') == '2026-08-24 12:55:00'
    assert format_beijing_datetime('2026-08-24T04:55:00+00:00') == '2026-08-24 12:55:00'


def test_iso_naive_string_no_shift() -> None:
    assert format_beijing_datetime('2026-08-24T20:00:00') == '2026-08-24 20:00:00'


def test_apply_beijing_times_on_payload() -> None:
    payload = {
        'createTime': datetime(2026, 8, 24, 4, 55, 0, tzinfo=timezone.utc),
        'title': 'hello',
        'nested': {'pubTime': '2026-08-24T04:55:00Z'},
    }
    out = apply_beijing_times(payload)
    assert out['createTime'] == '2026-08-24 12:55:00'
    assert out['title'] == 'hello'
    assert out['nested']['pubTime'] == '2026-08-24 12:55:00'
    assert 'Z' not in out['createTime']
    assert 'T' not in out['createTime']


def test_format_utc_as_beijing_naive_is_utc() -> None:
    naive = datetime(2026, 8, 25, 8, 15, 0)
    assert format_utc_as_beijing(naive) == '2026-08-25 16:15:00'
    aware = datetime(2026, 8, 25, 8, 15, 0, tzinfo=timezone.utc)
    assert format_utc_as_beijing(aware) == '2026-08-25 16:15:00'
    assert format_utc_as_beijing('2026-08-25T08:15:00Z') == '2026-08-25 16:15:00'


def test_encode_api_datetime_aware_utc_to_beijing() -> None:
    aware = datetime(2026, 8, 25, 8, 15, 0, tzinfo=timezone.utc)
    assert encode_api_datetime(aware) == '2026-08-25 16:15:00'
    naive = datetime(2026, 8, 25, 20, 0, 0)
    assert encode_api_datetime(naive) == '2026-08-25 20:00:00'


def test_eastmoney_style_naive_pub_time_not_shifted() -> None:
    """东财 showTime 是北京本地朴素值；序列化不得再 +8。"""
    row = {
        'source': 'eastmoney',
        'title': '快讯',
        'pubTime': datetime(2026, 8, 24, 20, 15, 0),
        'createTime': datetime(2026, 8, 24, 12, 15, 0, tzinfo=timezone.utc),
    }
    out = apply_beijing_times(row)
    assert out['pubTime'] == '2026-08-24 20:15:00'
    assert out['createTime'] == '2026-08-24 20:15:00'


def test_now_beijing_is_naive_shanghai_wall_clock() -> None:
    stamp = now_beijing()
    assert stamp.tzinfo is None
    expected = datetime.now(BEIJING_TZ).replace(tzinfo=None)
    assert abs((stamp - expected).total_seconds()) < 2
    encoded = encode_api_datetime(stamp)
    assert 'Z' not in encoded
    assert 'T' not in encoded


def test_fmt_influx_minute_utc_to_beijing() -> None:
    from utils.influx_util import _fmt_influx_minute

    utc = datetime(2026, 8, 25, 8, 15, tzinfo=timezone.utc)
    assert _fmt_influx_minute(utc) == '2026-08-25 16:15'
    naive_utc = datetime(2026, 8, 25, 8, 15)
    assert _fmt_influx_minute(naive_utc) == '2026-08-25 16:15'
    assert 'Z' not in _fmt_influx_minute(utc)


def test_heat_as_of_time_aware_utc_to_beijing() -> None:
    from module_market.service.heat_service import MarketHeatService

    row = SimpleNamespace(
        market='US',
        trade_date='2026-08-25',
        index_symbol='^GSPC',
        index_name='S&P 500',
        index_change_pct=1.0,
        total_turnover=1.0,
        advance_count=1,
        decline_count=1,
        flat_count=0,
        heat_score=50,
        heat_summary='x',
        currency='USD',
        filter_rule='',
        weights_json='{}',
        as_of_time=datetime(2026, 8, 25, 8, 15, 0, tzinfo=timezone.utc),
        status='ok',
        message=None,
    )
    out = MarketHeatService._serialize_heat(row)
    assert out['asOfTime'] == '2026-08-25 16:15:00'
    assert 'Z' not in out['asOfTime']

    row.as_of_time = datetime(2026, 8, 25, 16, 15, 0)
    naive_out = MarketHeatService._serialize_heat(row)
    assert naive_out['asOfTime'] == '2026-08-25 16:15:00'

    top = MarketHeatService._serialize_top50(
        [
            SimpleNamespace(
                rank_no=1,
                symbol='AAPL',
                name='Apple',
                market_cap=1,
                turnover=1,
                change_pct=1,
                currency='USD',
                as_of_time=datetime(2026, 8, 25, 8, 15, 0, tzinfo=timezone.utc),
            )
        ]
    )
    assert top[0]['asOfTime'] == '2026-08-25 16:15:00'


def test_fmt_ts_iso_z_and_news_datetime_to_beijing() -> None:
    from module_quant.service.longbridge_quote import fmt_ts, map_news_item

    assert fmt_ts('2026-08-25T08:15:00Z', with_time=True) == '2026-08-25 16:15:00'
    assert fmt_ts('2026-08-25T08:15:00+00:00', with_time=True) == '2026-08-25 16:15:00'
    # 已格式化的北京墙上时钟不得二次 +8（assemble_quote_snapshot 会再走 fmt_ts）
    assert fmt_ts('2026-08-25 16:15:00', with_time=True) == '2026-08-25 16:15:00'
    news = map_news_item(
        SimpleNamespace(
            id='1',
            title='Apple beats',
            url='https://x',
            published_at=datetime(2026, 8, 25, 8, 15, 0, tzinfo=timezone.utc),
        )
    )
    assert news is not None
    assert news['time'] == '2026-08-25 16:15:00'
    assert 'Z' not in news['time']
    dumped = map_news_item(
        SimpleNamespace(id='2', title='naive dump', url='', published_at='2026-08-25 08:15:00+00:00')
    )
    assert dumped is not None
    assert dumped['time'] == '2026-08-25 16:15:00'


@pytest.mark.asyncio
async def test_dashboard_generated_at_uses_now_beijing() -> None:
    from module_dashboard.service import dashboard_service
    from module_dashboard.service.dashboard_service import DashboardService

    frozen = datetime(2026, 8, 25, 16, 15, 0)
    sections = {key: {'ok': True, 'reason': None, 'data': {}} for key in dashboard_service.SECTION_PERMS}
    with (
        patch('module_dashboard.service.dashboard_service.now_beijing', return_value=frozen),
        patch('module_dashboard.service.dashboard_service.cache_get_json', new=AsyncMock(return_value=None)),
        patch.object(DashboardService, '_collect', new=AsyncMock(return_value=sections)),
        patch('module_dashboard.service.dashboard_service.cache_set_json', new=AsyncMock()),
    ):
        result = await DashboardService.get_summary_services(AsyncMock(), 1, ['*:*:*'], use_cache=False)
    assert result['generatedAt'] == '2026-08-25 16:15:00'
    assert 'Z' not in result['generatedAt']


@pytest.mark.asyncio
async def test_readmodel_user_facing_timestamps_use_now_beijing() -> None:
    from module_quant.service.longbridge_service import LongbridgeService
    from module_quant.service.readmodel_service import ReadModelService

    frozen = datetime(2026, 8, 25, 16, 15, 0)
    with (
        patch.object(ReadModelService, '_get', new=AsyncMock(return_value=None)),
        patch.object(ReadModelService, '_set', new=AsyncMock()),
        patch.object(ReadModelService, 'get_scheduled', new=AsyncMock(return_value=None)),
        patch('module_quant.service.readmodel_service.now_beijing', return_value=frozen),
        patch.object(LongbridgeService, 'get_account_balance_async', new=AsyncMock(return_value={})),
        patch.object(
            LongbridgeService,
            'flatten_account',
            return_value={
                'configured': True,
                'totalCash': 1,
                'netAssets': 1,
                'availableCash': 1,
                'currency': 'HKD',
            },
        ),
        patch.object(
            LongbridgeService,
            'get_positions_async',
            new=AsyncMock(return_value={'configured': True, 'positions': []}),
        ),
    ):
        asset = await ReadModelService.get_account_asset_snapshot(use_scheduled=False)
        overview = await ReadModelService.get_platform_overview_snapshot()
    assert asset['timestamp'] == '2026-08-25 16:15:00'
    assert overview['refreshTime'] == '2026-08-25 16:15:00'
    assert 'Z' not in asset['timestamp']
    assert 'Z' not in overview['refreshTime']
