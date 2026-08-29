"""个股实时价：腾讯文本解析、订阅归一化、批量拉取。"""

import os
import sys
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.controller.market_ws_controller import parse_client_frame
from module_market.service.live_quotes_service import (
    MAX_LIVE_SYMBOLS,
    LiveQuotesService,
    normalize_symbol_market,
    parse_subscribe_symbols,
    parse_symbols_query,
)
from module_market.service.quote_subscribe_hub import QuoteSubscribeHub
from module_market.service.tencent_quote import parse_gtimg_text
from module_quant.service.longbridge_service import LongbridgeService


def setup_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def teardown_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def _gtimg_line(code: str, name: str, last: str, prev: str, chg_pct: str, ts: str) -> str:
    parts = [''] * 33
    parts[1] = name
    parts[3] = last
    parts[4] = prev
    parts[30] = ts
    parts[32] = chg_pct
    return f'v_{code}="{"~".join(parts)}";'


def test_parse_gtimg_stock_line() -> None:
    text = _gtimg_line('usAAPL', '苹果', '227.52', '226.01', '0.67', '2026-08-29 10:00:00')
    quotes = parse_gtimg_text(text)
    assert quotes['usAAPL']['last'] == 227.52
    assert quotes['usAAPL']['prevClose'] == 226.01
    assert quotes['usAAPL']['changePct'] == 0.67
    assert quotes['usAAPL']['name'] == '苹果'


def test_normalize_symbol_suffixes() -> None:
    assert normalize_symbol_market('aapl.us', 'HK') == ('AAPL', 'US')
    assert normalize_symbol_market('00700.HK') == ('00700', 'HK')
    assert normalize_symbol_market('600519.SS') == ('600519', 'CN')
    assert normalize_symbol_market('') is None


def test_parse_subscribe_mixed_and_cap() -> None:
    pairs = parse_subscribe_symbols(
        ['AAPL:US', {'symbol': '00700', 'market': 'HK'}, 'AAPL.US', 'MSFT']
    )
    assert pairs == [('AAPL', 'US'), ('00700', 'HK'), ('MSFT', 'US')]
    huge = parse_subscribe_symbols([f'S{i}:US' for i in range(200)])
    assert len(huge) == MAX_LIVE_SYMBOLS


def test_parse_symbols_query() -> None:
    assert parse_symbols_query('AAPL:US, 00700.HK') == [('AAPL', 'US'), ('00700', 'HK')]
    assert parse_symbols_query(None) == []


def test_parse_client_frame_kinds() -> None:
    assert parse_client_frame('ping') == ('ping', None)
    assert parse_client_frame('{"type":"subscribe","symbols":["AAPL:US"]}')[0] == 'subscribe'
    kind, payload = parse_client_frame('{"type":"subscribe","symbols":["AAPL:US"]}')
    assert kind == 'subscribe'
    assert payload == [('AAPL', 'US')]
    kind, payload = parse_client_frame('{"type":"unsubscribe"}')
    assert kind == 'unsubscribe'
    assert payload == []


def test_fetch_items_maps_tencent_codes() -> None:
    payload = _gtimg_line('usAAPL', 'Apple', '100', '90', '11.11', '10:00:00')
    with (
        patch('module_market.service.live_quotes_service.is_live_kline_session', return_value=False),
        patch(
            'module_market.service.live_quotes_service.fetch_tencent_batch',
            return_value=parse_gtimg_text(payload),
        ),
    ):
        items = LiveQuotesService._fetch_items([('AAPL', 'US')])
    assert len(items) == 1
    assert items[0]['symbol'] == 'AAPL'
    assert items[0]['last'] == 100.0
    assert items[0]['changePct'] == 11.11
    assert items[0]['source'] == 'tencent'


def _live_us_only(market: str, now: object | None = None) -> bool:
    return str(market).upper() == 'US'


def test_fetch_items_live_us_longbridge_closed_hk_tencent() -> None:
    lb_quote = {
        'configured': True,
        'quotes': [
            {
                'symbol': 'AAPL.US',
                'lastDone': 320,
                'prevClose': 310,
                'changeRate': 3.2258,
                'timestamp': '2026-08-29 10:00:00',
            }
        ],
    }
    tencent_payload = _gtimg_line('hk00700', '腾讯', '400', '390', '2.56', '16:00:00')
    with (
        patch('module_market.service.live_quotes_service.is_live_kline_session', side_effect=_live_us_only),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_realtime_quote', return_value=lb_quote) as lb_fetch,
        patch(
            'module_market.service.live_quotes_service.fetch_tencent_batch',
            return_value=parse_gtimg_text(tencent_payload),
        ) as tx_fetch,
    ):
        items = LiveQuotesService._fetch_items([('AAPL', 'US'), ('00700', 'HK')])
    lb_fetch.assert_called_once()
    assert lb_fetch.call_args.args[0] == ['AAPL.US']
    tx_fetch.assert_called()
    tx_codes = [code for call in tx_fetch.call_args_list for code in call.args[0]]
    assert 'hk00700' in tx_codes
    assert all(not str(code).lower().startswith('us') for code in tx_codes)
    by_sym = {item['symbol']: item for item in items}
    assert by_sym['AAPL']['last'] == 320
    assert by_sym['AAPL']['source'] == 'longbridge'
    assert by_sym['AAPL']['quoteTime'] == '2026-08-29 10:00:00'
    assert by_sym['00700']['last'] == 400.0
    assert by_sym['00700']['source'] == 'tencent'


def test_fetch_items_maps_hk_700_to_00700() -> None:
    lb_quote = {
        'configured': True,
        'quotes': [{'symbol': '700.HK', 'lastDone': 455.2, 'prevClose': 447.8, 'changeRate': 1.65}],
    }
    with (
        patch('module_market.service.live_quotes_service.is_live_kline_session', return_value=True),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_realtime_quote', return_value=lb_quote),
        patch('module_market.service.live_quotes_service.fetch_tencent_batch') as tx_fetch,
    ):
        items = LiveQuotesService._fetch_items([('00700', 'HK')])
    tx_fetch.assert_not_called()
    assert items[0]['symbol'] == '00700'
    assert items[0]['last'] == 455.2
    assert items[0]['source'] == 'longbridge'


def test_fetch_items_longbridge_empty_circuit_uses_tencent() -> None:
    payload = _gtimg_line('usAAPL', 'Apple', '100', '90', '11.11', '10:00:00')
    with (
        patch('module_market.service.live_quotes_service.is_live_kline_session', return_value=True),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(
            LongbridgeService,
            'get_realtime_quote',
            return_value={'configured': True, 'quotes': [], 'reason': 'circuit_open'},
        ) as lb_fetch,
        patch(
            'module_market.service.live_quotes_service.fetch_tencent_batch',
            return_value=parse_gtimg_text(payload),
        ),
    ):
        items = LiveQuotesService._fetch_items([('AAPL', 'US')])
    lb_fetch.assert_called_once()
    assert len(items) == 1
    assert items[0]['source'] == 'tencent'
    assert items[0]['last'] == 100.0


@pytest.mark.asyncio
async def test_get_quotes_empty_skips_network() -> None:
    with patch('module_market.service.live_quotes_service.fetch_tencent_batch') as fetch:
        out = await LiveQuotesService.get_quotes([])
    assert out['items'] == []
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_get_quotes_uses_cache() -> None:
    cached = {'items': [{'symbol': 'AAPL', 'last': 1}], 'asOf': 't', 'source': 'tencent'}
    with (
        patch('module_market.service.live_quotes_service.cache_get_json', new=AsyncMock(return_value=cached)),
        patch('module_market.service.live_quotes_service.fetch_tencent_batch') as fetch,
    ):
        out = await LiveQuotesService.get_quotes([('AAPL', 'US')])
    assert out['cached'] is True
    assert out['items'][0]['symbol'] == 'AAPL'
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_get_quotes_payload_source_mix() -> None:
    lb_quote = {
        'configured': True,
        'quotes': [{'symbol': 'AAPL.US', 'lastDone': 320, 'prevClose': 310, 'changeRate': 3.22}],
    }
    tencent_payload = _gtimg_line('hk00700', '腾讯', '400', '390', '2.56', '16:00:00')
    with (
        patch('module_market.service.live_quotes_service.cache_get_json', new=AsyncMock(return_value=None)),
        patch('module_market.service.live_quotes_service.cache_set_json', new=AsyncMock()),
        patch('module_market.service.live_quotes_service.is_live_kline_session', side_effect=_live_us_only),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'get_realtime_quote', return_value=lb_quote),
        patch(
            'module_market.service.live_quotes_service.fetch_tencent_batch',
            return_value=parse_gtimg_text(tencent_payload),
        ),
    ):
        out = await LiveQuotesService.get_quotes([('AAPL', 'US'), ('00700', 'HK')])
    assert out['cached'] is False
    assert out['source'] == 'longbridge+tencent'
    by_sym = {item['symbol']: item for item in out['items']}
    assert by_sym['AAPL']['source'] == 'longbridge'
    assert by_sym['AAPL']['last'] == 320
    assert by_sym['00700']['source'] == 'tencent'


@pytest.mark.asyncio
async def test_get_quotes_hub_complete_skips_cache_and_fetch() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US', {'last_done': 321, 'prev_close': 300, 'timestamp': '2026-08-29 10:01:00'}
    )
    with (
        patch('module_market.service.live_quotes_service.cache_get_json', new=AsyncMock()) as cache_get,
        patch('module_market.service.live_quotes_service.cache_set_json', new=AsyncMock()) as cache_set,
        patch('module_market.service.live_quotes_service.fetch_tencent_batch') as tx_fetch,
        patch.object(LongbridgeService, 'get_realtime_quote') as lb_fetch,
    ):
        out = await LiveQuotesService.get_quotes([('AAPL', 'US')])
    cache_get.assert_not_called()
    cache_set.assert_not_called()
    tx_fetch.assert_not_called()
    lb_fetch.assert_not_called()
    assert out['cached'] is False
    assert out['source'] == 'longbridge'
    assert out['items'][0]['symbol'] == 'AAPL'
    assert out['items'][0]['last'] == 321
    assert out['items'][0]['source'] == 'longbridge'


@pytest.mark.asyncio
async def test_get_quotes_hub_subset_still_fetches_rest() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US', {'last_done': 321, 'prev_close': 300, 'timestamp': '2026-08-29 10:01:00'}
    )
    tencent_payload = _gtimg_line('usMSFT', 'Microsoft', '400', '390', '2.56', '16:00:00')
    with (
        patch('module_market.service.live_quotes_service.cache_get_json', new=AsyncMock(return_value=None)) as cache_get,
        patch('module_market.service.live_quotes_service.cache_set_json', new=AsyncMock()),
        patch('module_market.service.live_quotes_service.is_live_kline_session', return_value=False),
        patch.object(LongbridgeService, 'get_realtime_quote') as lb_fetch,
        patch(
            'module_market.service.live_quotes_service.fetch_tencent_batch',
            return_value=parse_gtimg_text(tencent_payload),
        ) as tx_fetch,
    ):
        out = await LiveQuotesService.get_quotes([('AAPL', 'US'), ('MSFT', 'US')])
    cache_get.assert_called()
    tx_fetch.assert_called()
    lb_fetch.assert_not_called()
    by_sym = {item['symbol']: item for item in out['items']}
    assert by_sym['AAPL']['last'] == 321
    assert by_sym['AAPL']['source'] == 'longbridge'
    assert by_sym['MSFT']['last'] == 400.0
    assert by_sym['MSFT']['source'] == 'tencent'
