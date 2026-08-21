import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.longbridge_quote import empty_depth
from module_quant.service.longbridge_service import LongbridgeService
from utils.longbridge_breaker import LongbridgeBreaker, is_auth_failure, is_timeout_failure


def setup_function() -> None:
    LongbridgeBreaker.reset()


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
    assert quote['reason'] == 'circuit_open'
    assert quote['quotes'] == []
    assert depth['reason'] == 'circuit_open'
    assert depth['asks'] == []
    assert trades['reason'] == 'circuit_open'
    assert content['news'] == []


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
