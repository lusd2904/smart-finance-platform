from unittest.mock import patch

from module_quant.service.longbridge_quote import is_auth_denied, quote_error_reason
from module_quant.service.longbridge_service import LongbridgeService


def test_is_auth_denied_401004() -> None:
    assert is_auth_denied('OpenApiException 401004 token expired')
    assert quote_error_reason(Exception('401004')) == 'unauthorized'


def test_depth_returns_empty_when_breaker_open() -> None:
    LongbridgeService._reset_auth_breaker()
    LongbridgeService._auth_fail_until = 10**12
    try:
        with patch.object(LongbridgeService, 'is_configured', return_value=True):
            data = LongbridgeService.get_depth('AAPL', 'US')
        assert data['asks'] == []
        assert data['bids'] == []
        assert data['reason'] == 'auth_tripped'
        assert data.get('available') is False
    finally:
        LongbridgeService._reset_auth_breaker()


def test_three_auth_failures_cut_off() -> None:
    LongbridgeService._reset_auth_breaker()
    try:
        for _ in range(3):
            LongbridgeService._trip_auth(Exception('401004 token invalid'))
        assert LongbridgeService._auth_cut_off is True
        msg = LongbridgeService._auth_blocked()
        assert msg and '切断' in msg
        with patch.object(LongbridgeService, 'is_configured', return_value=True):
            data = LongbridgeService.get_depth('AAPL', 'US')
        assert data['asks'] == []
        assert data['reason'] == 'auth_tripped'
    finally:
        LongbridgeService._reset_auth_breaker()
