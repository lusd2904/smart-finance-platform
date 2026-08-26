import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone

from module_market.service.kline_period import (
    default_range_start,
    is_minute_period,
    normalize_kline_period,
    resample_how,
)
from module_quant.service.longbridge_quote import (
    CN_NO_DEPTH_MSG,
    assemble_depth,
    assemble_trades,
    empty_depth,
    empty_trades,
    fmt_ts,
    is_cn_market,
    map_intraday_point,
    map_trade,
    map_trade_side,
    merge_position_quotes,
    merge_snapshot_with_db,
    overlay_last_bar,
    quote_error_message,
    quote_error_reason,
)


def test_normalize_kline_period_aliases() -> None:
    assert normalize_kline_period('分时') == 'intraday'
    assert normalize_kline_period('1分') == '1min'
    assert normalize_kline_period('5m') == '5min'
    assert normalize_kline_period('15min') == '15min'
    assert normalize_kline_period('日K') == 'daily'
    assert normalize_kline_period('周') == 'weekly'
    assert normalize_kline_period('月K') == 'monthly'
    assert is_minute_period('1min') is True
    assert is_minute_period('daily') is False
    assert resample_how('weekly') == 'W'
    assert default_range_start('monthly', '-2y') == '-5y'
    assert default_range_start('daily', '-10d') == '-10d'


def test_cn_and_unconfigured_depth_are_empty() -> None:
    assert is_cn_market('CN', '600519') is True
    assert is_cn_market('US', 'AAPL') is False
    cn = empty_depth('600519', 'CN', configured=True, reason='cn_no_depth', message=CN_NO_DEPTH_MSG)
    assert cn['available'] is False
    assert cn['asks'] == []
    assert cn['bids'] == []
    assert 'A股暂无实时盘口' in (cn['message'] or '')
    us = empty_depth('AAPL', 'US', configured=False, reason='unconfigured', message='长桥凭据未配置，盘口暂不可用')
    assert us['configured'] is False
    assert us['asks'] == []


def test_assemble_depth_maps_sdk_object_without_inventing() -> None:
    raw = SimpleNamespace(
        symbol='700.HK',
        asks=[SimpleNamespace(position=1, price='360.2', volume=2000, order_num=2)],
        bids=[],
    )
    data = assemble_depth(raw, '700', 'HK', '700.HK')
    assert data['available'] is True
    assert data['lbSymbol'] == '700.HK'
    assert len(data['asks']) == 1
    assert data['asks'][0]['price'] == 360.2
    assert data['bids'] == []
    empty = assemble_depth(SimpleNamespace(asks=[], bids=[]), 'AAPL', 'US', 'AAPL.US')
    assert empty['asks'] == []
    assert empty['bids'] == []
    assert empty['available'] is False


def test_assemble_quote_snapshot_prefers_calc_and_derives_gaps() -> None:
    from module_quant.service.longbridge_quote import assemble_quote_snapshot, map_calc_index, map_static_info

    static = map_static_info(
        SimpleNamespace(
            symbol='AAPL.US',
            name_cn='苹果',
            currency='USD',
            lot_size=1,
            total_shares=15_000_000_000,
            circulating_shares=15_000_000_000,
            eps=10.0,
            eps_ttm=7.0,
            bps=5.0,
            dividend_yield=0.004,
        )
    )
    calc = map_calc_index(
        SimpleNamespace(
            pe_ttm_ratio=28.5,
            pb_ratio=None,
            total_market_value=None,
            turnover_rate=0.0023,
            volume_ratio=0.67,
            amplitude=0.018,
        )
    )
    snap = assemble_quote_snapshot(
        symbol='AAPL',
        market='US',
        lb_symbol='AAPL.US',
        quote={'last': 210.0, 'prevClose': 200.0, 'open': 201, 'high': 212, 'low': 199, 'volume': 1e6, 'turnover': 2e8},
        static=static,
        calc=calc,
        capital={'in': {'large': 10, 'medium': 5, 'small': 1}, 'out': {'large': 4, 'medium': 2, 'small': 1}, 'net': 9},
        high52=250.0,
        low52=150.0,
    )
    assert snap['peTtm'] == 28.5
    assert snap['peStatic'] == pytest.approx(21.0)  # 210 / 10
    assert snap['pb'] == pytest.approx(42.0)  # 210 / 5
    assert snap['marketCap'] == pytest.approx(210.0 * 15_000_000_000)
    assert snap['floatMarketCap'] == pytest.approx(210.0 * 15_000_000_000)
    assert snap['avgPrice'] == pytest.approx(200.0)
    assert snap['turnoverRate'] == pytest.approx(0.23)
    assert snap['dividendYield'] == pytest.approx(0.4)
    assert snap['volumeRatio'] == 0.67
    assert snap['name'] == '苹果'
    assert snap['capital']['net'] == 9
    assert snap['high52'] == 250.0
    assert snap['low52'] == 150.0
    assert snap['dividendTtm'] == pytest.approx(0.84)
    assert snap['historyHigh'] is None
    assert snap['beta'] is None


def test_merge_snapshot_with_db_fills_gaps_without_overwriting_live() -> None:
    live = {
        'available': True,
        'last': 310.34,
        'peTtm': 35.13,
        'high52': 344.57,
        'historyHigh': None,
        'name': '苹果',
    }
    db = {
        'last': 309.35,
        'historyHigh': 550.01,
        'historyLow': 6.12,
        'high52': 340.0,
        'category': 'mag7',
        'name': 'Apple Inc',
    }
    merged = merge_snapshot_with_db(live, db)
    assert merged['last'] == 310.34
    assert merged['peTtm'] == 35.13
    assert merged['high52'] == 344.57
    assert merged['historyHigh'] == 550.01
    assert merged['historyLow'] == 6.12
    assert merged['category'] == 'mag7'
    assert merged['name'] == '苹果'

    cn = merge_snapshot_with_db(
        {'available': False, 'symbol': '600519', 'market': 'CN'},
        {'last': 1688.0, 'historyHigh': 2000.0, 'name': '贵州茅台'},
    )
    assert cn['available'] is True
    assert cn['last'] == 1688.0
    assert cn['name'] == '贵州茅台'


def test_kline_high_low_and_news_mapping() -> None:
    from module_quant.service.longbridge_quote import kline_high_low, map_news_item

    high, low = kline_high_low(
        [
            {'high': 12, 'low': 8},
            {'high': 15, 'low': 9},
            {'high': 0, 'low': None},
        ]
    )
    assert high == 15
    assert low == 8
    news = map_news_item(SimpleNamespace(id='1', title='Apple beats', url='https://x', published_at='2026-08-24'))
    assert news is not None
    assert news['title'] == 'Apple beats'
    assert map_news_item(SimpleNamespace(title=None)) is None


def test_assemble_trades_and_side_mapping() -> None:
    raw = [
        SimpleNamespace(price='190.15', volume=100, timestamp=1710000000, direction=2, trade_type=' '),
        SimpleNamespace(price='190.10', volume=50, timestamp=1710000001, direction=1, trade_type='I'),
    ]
    data = assemble_trades(raw, 'AAPL', 'US', 'AAPL.US', 20)
    assert data['available'] is True
    assert len(data['trades']) == 2
    trade = map_trade(raw[0])
    assert trade['price'] == 190.15
    assert trade['side'] == 'buy'
    assert trade['time']
    assert map_trade_side(1) == 'sell'
    assert map_trade_side(0) == 'neutral'
    empty = assemble_trades([], 'AAPL', 'US', 'AAPL.US', 10)
    assert empty['trades'] == []


def test_unauthorized_is_empty_hint() -> None:
    exc = RuntimeError('401 Unauthorized')
    assert quote_error_reason(exc) == 'unauthorized'
    msg = quote_error_message(exc, '成交明细暂不可用')
    assert '凭证' in msg or '权限' in msg
    data = empty_trades('AAPL', 'US', configured=True, reason='unauthorized', message=msg)
    assert data['trades'] == []


def test_overlay_last_bar_does_not_create_bar() -> None:
    bars = [{'date': '2024-01-02', 'open': 10, 'high': 11, 'low': 9, 'close': 10.5, 'volume': 100}]
    overlay_last_bar(bars[0], 12.0)
    assert len(bars) == 1
    assert bars[0]['close'] == 12.0
    assert bars[0]['high'] == 12.0
    assert bars[0]['low'] == 9


def _kline_bar(close: float, date: str = '2024-06-04') -> dict:
    return {'date': date, 'open': close - 1, 'high': close + 1, 'low': close - 2, 'close': close, 'volume': 100}


@pytest.mark.asyncio
async def test_quote_kline_us_live_minute_prefers_longbridge_even_if_influx_has_bars() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock(return_value=[_kline_bar(11)])
    cs = AsyncMock(return_value={'klines': [_kline_bar(190.15)]})
    intra = AsyncMock()
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='pre'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', '1min', 200)
    cs.assert_awaited()
    assert cs.await_args.args[2] == '1min'
    assert cs.await_args.args[3] >= 500
    influx.assert_not_called()
    intra.assert_not_called()
    rt.assert_not_called()
    assert data['source'] == 'longbridge'
    assert data['priceSource'] == 'longbridge'
    assert data['session'] == 'pre'
    assert data.get('fallback') is None
    assert data['klines'][0]['close'] == 190.15
    assert data['quote']['last'] == 190.15


@pytest.mark.asyncio
async def test_quote_kline_us_live_intraday_uses_one_min_candlesticks_not_intraday() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock(return_value=[_kline_bar(11)])
    cs = AsyncMock(return_value={'klines': [_kline_bar(190.15, '2026-08-25 16:00:00')]})
    intra = AsyncMock(return_value={'klines': [_kline_bar(1.0)]})
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='pre'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', 'intraday', 200)
    cs.assert_awaited()
    assert cs.await_args.args[0] == 'AAPL'
    assert cs.await_args.args[1] == 'US'
    assert cs.await_args.args[2] == '1min'
    assert cs.await_args.args[3] >= 500
    intra.assert_not_called()
    influx.assert_not_called()
    rt.assert_not_called()
    assert data['source'] == 'longbridge'
    assert data['period'] == 'intraday'
    assert data['session'] == 'pre'
    assert data['klines'][0]['close'] == 190.15
    assert data['quote']['last'] == 190.15


@pytest.mark.asyncio
async def test_quote_kline_daily_always_influx_never_longbridge() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock(return_value=[])
    cs = AsyncMock()
    intra = AsyncMock()
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='regular'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', 'daily', 200)
    cs.assert_not_called()
    intra.assert_not_called()
    rt.assert_not_called()
    influx.assert_awaited()
    assert influx.await_args.args[0].period == 'daily'
    assert data['klines'] == []
    assert data['source'] == 'influx'
    assert data['priceSource'] == 'history'
    assert data.get('fallback') is None


@pytest.mark.asyncio
async def test_quote_kline_hk_closed_minute_uses_influx_daily() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    daily = [_kline_bar(360.2, '2024-06-04')]
    influx = AsyncMock(return_value=daily)
    cs = AsyncMock()
    intra = AsyncMock()
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=False),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='closed'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), '700', 'HK', '1min', 200)
    cs.assert_not_called()
    intra.assert_not_called()
    rt.assert_not_called()
    assert influx.await_args.args[0].period == 'daily'
    assert influx.await_args.args[0].symbol == '700'
    assert data['source'] == 'influx'
    assert data['fallback'] == 'daily'
    assert data['session'] == 'closed'
    assert data['message'] == '已收盘，显示当日日K'
    assert data['klines'][0]['close'] == 360.2


@pytest.mark.asyncio
async def test_quote_kline_cn_closed_minute_uses_influx_daily() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    daily = [_kline_bar(1688.0, '2024-06-04')]
    influx = AsyncMock(return_value=daily)
    cs = AsyncMock()
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=False),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='closed'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), '600519', 'CN', '1min', 200)
    cs.assert_not_called()
    rt.assert_not_called()
    assert influx.await_args.args[0].period == 'daily'
    assert influx.await_args.args[0].market == 'CN'
    assert data['source'] == 'influx'
    assert data['fallback'] == 'daily'
    assert data['session'] == 'closed'
    assert data['klines'][0]['close'] == 1688.0


@pytest.mark.asyncio
async def test_quote_kline_hk_live_intraday_uses_get_intraday() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock()
    cs = AsyncMock()
    intra = AsyncMock(return_value={'klines': [_kline_bar(360.2, '2024-06-04 10:01:00')]})
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='regular'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), '700', 'HK', 'intraday', 200)
    intra.assert_awaited()
    cs.assert_not_called()
    influx.assert_not_called()
    rt.assert_not_called()
    assert data['source'] == 'longbridge'
    assert data['period'] == 'intraday'
    assert data['klines'][0]['close'] == 360.2


@pytest.mark.asyncio
async def test_quote_kline_us_live_intraday_falls_back_to_get_intraday_when_candlesticks_empty() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock(return_value=[_kline_bar(11)])
    cs = AsyncMock(return_value={'klines': []})
    intra = AsyncMock(return_value={'klines': [_kline_bar(191.0, '2026-08-25 16:15:00')]})
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='pre'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', 'intraday', 200)
    cs.assert_awaited()
    assert cs.await_args.args[2] == '1min'
    intra.assert_awaited()
    influx.assert_not_called()
    rt.assert_not_called()
    assert data['source'] == 'longbridge'
    assert data['klines'][0]['close'] == 191.0


@pytest.mark.asyncio
async def test_quote_kline_live_minute_falls_back_to_influx_when_lb_empty() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    influx = AsyncMock(return_value=[_kline_bar(11)])
    cs = AsyncMock(return_value={'klines': []})
    intra = AsyncMock(return_value={'klines': []})
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', influx),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_candlesticks_async', cs),
        patch.object(LongbridgeService, 'get_intraday_async', intra),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
        patch('module_trade.service.trade_service.is_live_kline_session', return_value=True),
        patch('module_trade.service.trade_service.kline_session_tag', return_value='regular'),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', '1min', 200)
    cs.assert_awaited()
    intra.assert_awaited()
    rt.assert_not_called()
    assert influx.await_args.args[0].period == '1min'
    assert data['source'] == 'influx'
    assert data['priceSource'] == 'history'
    assert data.get('fallback') is None
    assert data['klines'][0]['close'] == 11


def test_merge_position_quotes_from_longbridge_realtime() -> None:
    positions = [
        {'symbol': 'AAPL.US', 'quantity': 10, 'costPrice': 100, 'currency': 'USD'},
        {'symbol': '00700.HK', 'quantity': 100, 'costPrice': 300, 'currency': 'HKD'},
    ]
    quotes = [
        {'symbol': 'AAPL.US', 'lastDone': 110.0, 'prevClose': 100.0},
        {'symbol': '700.HK', 'lastDone': 330.0, 'prevClose': 320.0},
    ]
    merged = merge_position_quotes(positions, quotes)
    assert merged[0]['last'] == 110.0
    assert merged[0]['prevClose'] == 100.0
    assert merged[1]['last'] == 330.0
    assert merged[1]['prevClose'] == 320.0


def test_fmt_ts_utc_converts_to_beijing() -> None:
    utc = datetime(2026, 8, 25, 8, 15, tzinfo=timezone.utc)
    assert fmt_ts(utc, with_time=True) == '2026-08-25 16:15:00'
    naive_utc = datetime(2026, 8, 25, 8, 15)
    assert fmt_ts(naive_utc, with_time=True).endswith('16:15:00')
    point = map_intraday_point({'timestamp': utc, 'price': 310.1, 'volume': 1})
    assert point['date'] == '2026-08-25 16:15:00'
    assert point['close'] == 310.1


def test_us_minute_candlesticks_request_all_sessions() -> None:
    from module_quant.service.longbridge_service import LongbridgeService

    ctx = MagicMock()
    ctx.candlesticks = MagicMock(return_value=[])
    ctx.intraday = MagicMock(return_value=[])
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, '_blocked', return_value=False),
        patch.object(LongbridgeService, '_build_quote_context', return_value=ctx),
        patch.object(LongbridgeService, '_resolve_lb_period', return_value='Min_1'),
    ):
        LongbridgeService.get_candlesticks('AAPL', 'US', '1min', 40)
        LongbridgeService.get_intraday('AAPL', 'US')
    assert ctx.candlesticks.called
    assert ctx.intraday.called
    cs_kwargs = ctx.candlesticks.call_args.kwargs
    intra_kwargs = ctx.intraday.call_args.kwargs
    sessions = cs_kwargs.get('trade_sessions')
    assert sessions is not None
    assert str(sessions).endswith('All') or getattr(sessions, 'name', '') == 'All'
    assert intra_kwargs.get('trade_sessions') == sessions


if __name__ == '__main__':
    test_normalize_kline_period_aliases()
    test_cn_and_unconfigured_depth_are_empty()
    test_assemble_depth_maps_sdk_object_without_inventing()
    test_assemble_trades_and_side_mapping()
    test_unauthorized_is_empty_hint()
    test_overlay_last_bar_does_not_create_bar()
    print('ok')
