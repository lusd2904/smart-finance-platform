import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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
    is_cn_market,
    map_trade,
    map_trade_side,
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


@pytest.mark.asyncio
async def test_quote_kline_skips_realtime_when_influx_has_bars() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    bars = [{'date': '2024-06-04', 'open': 10, 'high': 12, 'low': 9, 'close': 11, 'volume': 100}]
    rt = AsyncMock()
    with (
        patch.object(MarketService, 'get_kline_services', new=AsyncMock(return_value=bars)),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', 'daily', 200)
    rt.assert_not_called()
    assert data['source'] == 'influx'
    assert data['priceSource'] == 'history'
    assert data['klines'][0]['close'] == 11
    assert data['quote']['last'] == 11


@pytest.mark.asyncio
async def test_quote_kline_fetches_realtime_only_when_influx_empty() -> None:
    from module_market.service.market_service import MarketService
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.trade_service import TradeService

    rt = AsyncMock(
        return_value={
            'configured': True,
            'quotes': [{'lastDone': 190.15, 'open': 189, 'high': 191, 'low': 188, 'volume': 10}],
        }
    )
    with (
        patch.object(MarketService, 'get_kline_services', new=AsyncMock(return_value=[])),
        patch.object(TradeService, '_ensure', new=AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_intraday_async', new=AsyncMock(return_value={'klines': []})),
        patch.object(LongbridgeService, 'get_realtime_quote_async', rt),
    ):
        data = await TradeService.get_quote_kline_services(MagicMock(), 'AAPL', 'US', 'daily', 200)
    rt.assert_awaited()
    assert data['klines'] == []
    assert data['priceSource'] == 'longbridge'
    assert data['quote']['last'] == 190.15


if __name__ == '__main__':
    test_normalize_kline_period_aliases()
    test_cn_and_unconfigured_depth_are_empty()
    test_assemble_depth_maps_sdk_object_without_inventing()
    test_assemble_trades_and_side_mapping()
    test_unauthorized_is_empty_hint()
    test_overlay_last_bar_does_not_create_bar()
    print('ok')
