import asyncio
import hashlib
from unittest.mock import patch

from module_quant.service.longbridge.auth import run_in_executor_with_context
from module_quant.service.longbridge_quote import is_auth_denied, quote_error_reason
from module_quant.service.longbridge_service import LongbridgeService
from utils.longbridge_breaker import LongbridgeBreaker


def _reset_auth_state() -> None:
    LongbridgeService._reset_auth_breaker()
    LongbridgeService.set_credentials(None)
    LongbridgeBreaker.reset()
    LongbridgeBreaker._seen_creds_epoch = 0
    LongbridgeBreaker._cached_remote_epoch = 0
    LongbridgeBreaker._epoch_refresh_pending = False


def test_is_auth_denied_401004() -> None:
    assert is_auth_denied('OpenApiException 401004 token expired')
    assert quote_error_reason(Exception('401004')) == 'unauthorized'


def test_depth_returns_empty_when_breaker_open() -> None:
    _reset_auth_state()
    LongbridgeService._auth_fail_until = 10**12
    try:
        with patch.object(LongbridgeService, 'is_configured', return_value=True):
            data = LongbridgeService.get_depth('AAPL', 'US')
        assert data['asks'] == []
        assert data['bids'] == []
        assert data['reason'] == 'auth_tripped'
        assert data.get('available') is False
    finally:
        _reset_auth_state()


def test_three_auth_failures_cut_off() -> None:
    _reset_auth_state()
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
        _reset_auth_state()


def test_set_credentials_same_token_clears_cut_off() -> None:
    """重存相同 token 也必须解除切断（不再要求签名变化）。"""
    _reset_auth_state()
    creds = {
        'app_key': 'shared-key',
        'app_secret': 'shared-secret',
        'access_token': 'same-token',
        'region': 'cn',
        'user_id': '101',
    }
    try:
        LongbridgeService.set_credentials(creds)
        sig = LongbridgeService._get_creds_signature(LongbridgeService.resolve_credentials())
        LongbridgeService._auth_cut_off = True
        LongbridgeService._auth_cut_off_sig = sig
        LongbridgeService._auth_fail_until = 10**12
        LongbridgeService.set_credentials(creds)
        assert LongbridgeService._auth_cut_off is False
        assert LongbridgeService._auth_blocked() is None
    finally:
        _reset_auth_state()


def test_creds_epoch_clears_cut_off() -> None:
    """其他进程 bump 的 creds_epoch 必须清掉本进程切断与熔断。"""
    _reset_auth_state()
    try:
        LongbridgeService._auth_cut_off = True
        LongbridgeService._auth_fail_until = 10**12
        LongbridgeBreaker.trip('unauthorized', 60)
        assert LongbridgeService._auth_blocked() is not None
        assert LongbridgeBreaker.allow() is False
        LongbridgeBreaker._seen_creds_epoch = 1
        LongbridgeBreaker._cached_remote_epoch = 2
        assert LongbridgeService._blocked() is False
        assert LongbridgeService._auth_cut_off is False
        assert LongbridgeBreaker.allow() is True
    finally:
        _reset_auth_state()


def test_creds_epoch_pull_from_redis_clears_cut_off() -> None:
    _reset_auth_state()

    class _Redis:
        async def get(self, key: str) -> str:
            assert key == 'sfp:lb:creds_epoch'
            return '7'

    async def _run() -> None:
        LongbridgeService._auth_cut_off = True
        LongbridgeBreaker.trip('unauthorized', 60)
        LongbridgeBreaker._seen_creds_epoch = 3
        with patch('utils.longbridge_breaker._redis_client', return_value=_Redis()):
            applied = await LongbridgeBreaker.pull_creds_epoch()
        assert applied is True
        assert LongbridgeService._auth_cut_off is False
        assert LongbridgeBreaker.allow() is True
        assert LongbridgeBreaker._seen_creds_epoch == 7

    try:
        asyncio.run(_run())
    finally:
        _reset_auth_state()


def test_get_today_orders_none_ctx() -> None:
    _reset_auth_state()
    try:
        with (
            patch.object(LongbridgeService, 'is_configured', return_value=True),
            patch.object(LongbridgeService, '_blocked', return_value=False),
            patch.object(LongbridgeService, '_build_trade_context', return_value=None),
        ):
            data = LongbridgeService.get_today_orders()
        assert data['configured'] is True
        assert data['orders'] == []
        assert data.get('reason') == 'unavailable'
        assert '不可用' in (data.get('message') or '')
    finally:
        _reset_auth_state()


def test_get_history_orders_none_ctx() -> None:
    _reset_auth_state()
    try:
        with (
            patch.object(LongbridgeService, 'is_configured', return_value=True),
            patch.object(LongbridgeService, '_blocked', return_value=False),
            patch.object(LongbridgeService, '_build_trade_context', return_value=None),
        ):
            data = LongbridgeService.get_history_orders()
        assert data['configured'] is True
        assert data['orders'] == []
        assert data.get('reason') == 'unavailable'
    finally:
        _reset_auth_state()


def _credential_fingerprint() -> tuple[str, str]:
    """返回 (source, token sha256 前缀)，测试断言不打印明文 token。"""
    resolved = LongbridgeService.resolve_credentials()
    token = str(resolved.get('access_token') or '')
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]
    return str(resolved.get('source') or ''), digest


def test_run_in_executor_with_context_sees_task_credentials() -> None:
    """异步任务 set_credentials 后：裸 executor 看到 env，copy_context helper 看到 DB。"""
    _reset_auth_state()
    db_token = 'task-db-access-token'
    env_token = 'stale-env-access-token'
    db_fp = hashlib.sha256(db_token.encode('utf-8')).hexdigest()[:16]
    env_fp = hashlib.sha256(env_token.encode('utf-8')).hexdigest()[:16]
    LongbridgeService.set_credentials(
        {
            'app_key': 'task-app-key',
            'app_secret': 'task-app-secret',
            'access_token': db_token,
            'region': 'cn',
            'user_id': '101',
        }
    )
    env_cfg = type(
        'EnvLB',
        (),
        {
            'longport_app_key': 'env-app-key',
            'longport_app_secret': 'env-app-secret',
            'longport_access_token': env_token,
            'longport_region': 'cn',
        },
    )()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        with patch('config.env.LongbridgeConfig', env_cfg):
            source, digest = await run_in_executor_with_context(loop, _credential_fingerprint)
            assert source == 'db'
            assert digest == db_fp
            raw_source, raw_digest = await loop.run_in_executor(None, _credential_fingerprint)
            assert raw_source == 'env'
            assert raw_digest == env_fp

    try:
        asyncio.run(_run())
    finally:
        _reset_auth_state()
