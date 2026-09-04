import asyncio
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.longbridge_quote import empty_depth
from module_quant.service.longbridge_service import LongbridgeService
from utils.longbridge_breaker import (
    CREDS_EPOCH_KEY,
    REDIS_KEY,
    LongbridgeBreaker,
    is_auth_failure,
    is_timeout_failure,
)


def setup_function() -> None:
    LongbridgeBreaker.reset()
    LongbridgeBreaker._seen_creds_epoch = 0
    LongbridgeBreaker._cached_remote_epoch = 0
    LongbridgeBreaker._epoch_refresh_pending = False
    LongbridgeService._reset_auth_breaker()


def test_auth_and_timeout_detection() -> None:
    assert is_auth_failure('OpenApiException 401004 token invalid')
    assert is_auth_failure('Unauthorized')
    assert is_timeout_failure('Read timed out')
    assert not is_auth_failure('rate limited 429')


def test_401004_trips_immediately_and_blocks_quote_paths() -> None:
    LongbridgeBreaker.record_failure(RuntimeError('401004 access token invalid'))
    snap = LongbridgeBreaker.snapshot()
    assert snap['open'] is True
    assert snap['reason'] == 'unauthorized'

    with patch.object(LongbridgeService, 'is_configured', return_value=True):
        quote = LongbridgeService.get_realtime_quote(['AAPL.US'])
        depth = LongbridgeService.get_depth('AAPL', 'US')
        trades = LongbridgeService.get_trades('AAPL', 'US')
        content = LongbridgeService.fetch_symbol_content('AAPL.US', ['news'])
        static = LongbridgeService.get_static_info(['AAPL.US'])
    assert quote['reason'] == 'circuit_open'
    assert quote['quotes'] == []
    assert depth['reason'] == 'circuit_open'
    assert depth['asks'] == []
    assert trades['reason'] == 'circuit_open'
    assert content['news'] == []
    assert static['reason'] == 'circuit_open'
    assert static['items'] == []


def test_timeouts_open_after_threshold() -> None:
    LongbridgeBreaker.record_failure(TimeoutError('timeout'))
    assert LongbridgeBreaker.allow() is True
    LongbridgeBreaker.record_failure(TimeoutError('timed out'))
    assert LongbridgeBreaker.allow() is False
    assert LongbridgeBreaker.snapshot()['reason'] == 'timeout'


def test_empty_depth_helper_still_cn_safe() -> None:
    data = empty_depth('600519', 'CN', configured=True, reason='cn_no_depth', message='A股暂无实时盘口')
    assert data['asks'] == []
    assert data['available'] is False


def test_persist_open_awaits_async_setex() -> None:
    calls: list[tuple[str, int, str]] = []

    class _Redis:
        async def setex(self, key: str, seconds: int, value: str) -> bool:
            calls.append((key, int(seconds), str(value)))
            return True

    async def _run() -> None:
        with patch('utils.longbridge_breaker._redis_client', return_value=_Redis()):
            LongbridgeBreaker.trip('unauthorized', 30)
            await asyncio.sleep(0)
        assert calls
        assert calls[0][0] == REDIS_KEY
        assert calls[0][1] == 30
        assert calls[0][2].startswith('unauthorized|')

    asyncio.run(_run())


def test_clear_persisted_deletes_circuit_key() -> None:
    deleted: list[str] = []

    class _Redis:
        async def delete(self, key: str) -> int:
            deleted.append(key)
            return 1

        async def incr(self, key: str) -> int:
            assert key == CREDS_EPOCH_KEY
            return 4

    async def _run() -> None:
        LongbridgeBreaker.trip('unauthorized', 30)
        assert LongbridgeBreaker.allow() is False
        with patch('utils.longbridge_breaker._redis_client', return_value=_Redis()):
            LongbridgeBreaker.reset()
            await LongbridgeBreaker.clear_persisted()
            epoch = await LongbridgeBreaker.bump_creds_epoch()
        assert deleted == [REDIS_KEY]
        assert epoch == 4
        assert LongbridgeBreaker.allow() is True
        assert LongbridgeBreaker._seen_creds_epoch == 4

    asyncio.run(_run())
