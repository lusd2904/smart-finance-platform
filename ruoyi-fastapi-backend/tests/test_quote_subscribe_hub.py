"""长桥行情订阅枢纽：推送映射、watch 并集、覆盖 live quotes。"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.live_quotes_service import LiveQuotesService
from module_market.service.quote_subscribe_hub import QuoteSubscribeHub, map_push_quote
from module_quant.service.longbridge_service import LongbridgeService


def setup_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def teardown_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def test_map_push_quote_and_prev_close_reuse() -> None:
    first = map_push_quote(
        'AAPL.US',
        {'last_done': 100, 'prev_close': 90, 'timestamp': '2026-08-29 10:00:00', 'name': 'Apple'},
    )
    assert first is not None
    assert first['symbol'] == 'AAPL'
    assert first['market'] == 'US'
    assert first['last'] == 100
    assert first['prevClose'] == 90
    assert first['source'] == 'longbridge'
    QuoteSubscribeHub.ingest_push('AAPL.US', {'last_done': 100, 'prev_close': 90})
    updated = QuoteSubscribeHub.ingest_push('AAPL.US', {'last_done': 110})
    assert updated is not None
    assert updated['last'] == 110
    assert updated['prevClose'] == 90
    assert updated['changePct'] == round((110 / 90 - 1) * 100, 2)


def test_watch_union_and_unwatch() -> None:
    calls: list[list[str]] = []

    def fake_sub(symbols):
        calls.append(list(symbols))
        return {'ok': True, 'subscribed': symbols}

    with (
        patch('module_quant.service.longbridge_service.LongbridgeService.is_configured', return_value=True),
        patch('module_quant.service.longbridge_service.LongbridgeService._blocked', return_value=False),
        patch('module_quant.service.longbridge_service.LongbridgeService.subscribe_quotes', side_effect=fake_sub),
        patch('module_quant.service.longbridge_service.LongbridgeService.unsubscribe_quotes', return_value={'ok': True}),
        patch('module_quant.service.longbridge_service.LongbridgeService.set_quote_handler', return_value={'ok': True}),
        patch(
            'module_quant.service.longbridge_service.LongbridgeService.get_realtime_quote',
            return_value={'quotes': []},
        ),
    ):
        asyncio.run(QuoteSubscribeHub.watch('a', [('AAPL', 'US')]))
        asyncio.run(QuoteSubscribeHub.watch('b', [('AAPL', 'US'), ('MSFT', 'US')]))
        assert QuoteSubscribeHub.subscribed_count() >= 1
        asyncio.run(QuoteSubscribeHub.unwatch('a'))
        asyncio.run(QuoteSubscribeHub.unwatch('b'))
        assert QuoteSubscribeHub.subscribed_count() == 0
    assert calls


def test_get_quotes_overlays_hub_on_cache() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US', {'last_done': 321, 'prev_close': 300, 'timestamp': '2026-08-29 10:01:00'}
    )
    cached = {
        'items': [
            {'symbol': 'AAPL', 'market': 'US', 'last': 1, 'source': 'tencent'},
            {'symbol': 'MSFT', 'market': 'US', 'last': 2, 'source': 'tencent'},
        ],
        'asOf': 't',
        'source': 'tencent',
    }

    async def _run() -> None:
        with patch('module_market.service.live_quotes_service.cache_get_json', new=AsyncMock(return_value=cached)):
            out = await LiveQuotesService.get_quotes([('AAPL', 'US'), ('MSFT', 'US')])
        assert out['cached'] is True
        by_sym = {item['symbol']: item for item in out['items']}
        assert by_sym['AAPL']['last'] == 321
        assert by_sym['AAPL']['source'] == 'longbridge'
        assert by_sym['MSFT']['last'] == 2
        assert by_sym['MSFT']['source'] == 'tencent'

    asyncio.run(_run())


def _snapshot_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.quote = MagicMock(return_value=[SimpleNamespace(last_done=1.0, prev_close=1.0, timestamp='')])
    ctx.static_info = MagicMock(
        return_value=[SimpleNamespace(symbol='AAPL.US', name_cn='苹果', currency='USD', lot_size=1)]
    )
    ctx.calc_indexes = MagicMock(return_value=[])
    ctx.capital_distribution = MagicMock(return_value=None)
    return ctx


def test_hub_security_quote_prefers_push_last() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US',
        {'last_done': 190.5, 'prev_close': 180, 'timestamp': '2026-08-29 10:00:00'},
    )
    quote = LongbridgeService._hub_security_quote('AAPL', 'US')
    assert quote is not None
    assert quote['last'] == 190.5
    assert quote['prevClose'] == 180
    assert quote['symbol'] == 'AAPL'
    assert quote.get('timestamp') or quote.get('quoteTime')


def test_get_quote_snapshot_skips_ctx_quote_when_hub_has_last() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US',
        {'last_done': 190.5, 'prev_close': 180, 'timestamp': '2026-08-29 10:00:00'},
    )
    ctx = _snapshot_ctx()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, '_blocked', return_value=False),
        patch.object(LongbridgeService, '_build_quote_context', return_value=ctx),
    ):
        snap = LongbridgeService.get_quote_snapshot('AAPL', 'US')
    ctx.quote.assert_not_called()
    ctx.static_info.assert_called()
    assert snap['last'] == 190.5
    assert snap['prevClose'] == 180
    assert snap['available'] is True


def test_get_quote_snapshot_uses_ctx_quote_on_hub_miss() -> None:
    ctx = _snapshot_ctx()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, '_blocked', return_value=False),
        patch.object(LongbridgeService, '_build_quote_context', return_value=ctx),
    ):
        snap = LongbridgeService.get_quote_snapshot('AAPL', 'US')
    ctx.quote.assert_called_once()
    assert snap['last'] == 1.0
