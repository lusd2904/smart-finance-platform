import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.dao.quant_dao import ADMIN_LONGBRIDGE_USER_ID, QuantLongbridgeConfigDao
from module_quant.entity.vo.quant_vo import QuantLongbridgeConfigModel
from module_quant.service.longbridge_service import (
    LongbridgeService,
    peek_request_user_id,
    resolve_longbridge_user_id,
)
from module_quant.service.quant_service import QuantService
from utils.longbridge_breaker import LongbridgeBreaker


def _row(**kwargs):
    defaults = {
        'id': 1,
        'user_id': ADMIN_LONGBRIDGE_USER_ID,
        'app_key': '',
        'app_secret': '',
        'access_token': '',
        'region': 'cn',
        'auto_trade_enabled': '0',
        'update_time': None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_resolve_user_id_prefers_arg_then_admin() -> None:
    assert resolve_longbridge_user_id(7) == 7
    assert peek_request_user_id() is None
    assert resolve_longbridge_user_id(None) is None
    assert resolve_longbridge_user_id(None, allow_admin_fallback=True) == ADMIN_LONGBRIDGE_USER_ID


def test_mask_treats_stars_as_unchanged() -> None:
    assert QuantService._is_masked('****wxyz') is True
    assert QuantService._is_masked('real-token-value') is False
    assert QuantService._mask('abcdefghij') == '****ghij'
    assert QuantService._mask('') == ''


def test_two_users_get_only_own_masked_config() -> None:
    store = {
        2: _row(id=2, user_id=2, app_key='user2-key', app_secret='user2-secret', access_token='user2-token-aaaa'),
        3: _row(id=3, user_id=3, app_key='user3-key', app_secret='user3-secret', access_token='user3-token-bbbb'),
    }

    async def fake_get(_db, user_id=None):
        target = user_id if user_id is not None else ADMIN_LONGBRIDGE_USER_ID
        return store.get(int(target))

    async def _run() -> None:
        with patch.object(QuantLongbridgeConfigDao, 'get_config', fake_get):
            cfg2 = await QuantService.get_longbridge_config_services(MagicMock(), 2)
            cfg3 = await QuantService.get_longbridge_config_services(MagicMock(), 3)
            empty = await QuantService.get_longbridge_config_services(MagicMock(), 99)
        assert cfg2.app_key == 'user2-key'
        assert cfg2.access_token == '****aaaa'
        assert cfg2.user_id == 2
        assert cfg3.app_key == 'user3-key'
        assert cfg3.access_token == '****bbbb'
        assert cfg3.user_id == 3
        assert empty.app_key == ''
        assert empty.access_token == ''
        assert empty.user_id == 99

    asyncio.run(_run())


def test_save_keeps_masked_secrets_and_writes_current_user() -> None:
    store: dict[int, SimpleNamespace] = {
        5: _row(
            id=10,
            user_id=5,
            app_key='old-key',
            app_secret='stored-secret',
            access_token='stored-token',
        )
    }
    saved: dict = {}

    async def fake_get(_db, user_id=None):
        return store.get(int(user_id if user_id is not None else ADMIN_LONGBRIDGE_USER_ID))

    async def fake_save(_db, config, user_id=None):
        saved.update(config)
        saved['resolved_user_id'] = user_id
        return store[5]

    async def _run() -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        payload = QuantLongbridgeConfigModel(
            userId=1,
            appKey='new-key',
            appSecret='****cret',
            accessToken='****oken',
            region='hk',
        )
        with (
            patch.object(QuantLongbridgeConfigDao, 'get_config', fake_get),
            patch.object(QuantLongbridgeConfigDao, 'save_config', fake_save),
            patch.object(QuantLongbridgeConfigDao, 'list_by_app_key', AsyncMock(return_value=[store[5]])),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(LongbridgeBreaker, 'clear_persisted', AsyncMock()),
            patch.object(LongbridgeBreaker, 'bump_creds_epoch', AsyncMock(return_value=1)),
        ):
            result = await QuantService.save_longbridge_config_services(db, payload, user_id=5)
        assert result.is_success is True
        assert saved['user_id'] == 5
        assert saved['resolved_user_id'] == 5
        assert saved['app_key'] == 'new-key'
        assert saved['app_secret'] == 'stored-secret'
        assert saved['access_token'] == 'stored-token'
        assert saved['region'] == 'hk'

    asyncio.run(_run())


def test_ensure_credentials_skips_admin_without_user_context() -> None:
    seen: list[int | None] = []

    async def fake_get(_db, user_id=None):
        seen.append(user_id)

    async def _run() -> None:
        LongbridgeService.set_credentials({'app_key': 'stale', 'user_id': '1'})
        with (
            patch.object(QuantLongbridgeConfigDao, 'get_config', fake_get),
            patch(
                'module_quant.service.longbridge.auth.peek_request_user_id',
                return_value=None,
            ),
        ):
            await LongbridgeService.ensure_credentials_from_db(MagicMock())
            creds = LongbridgeService.resolve_credentials()
            await LongbridgeService.ensure_credentials_from_db(MagicMock(), user_id=8)
        assert seen == [8]
        assert creds.get('source') != 'db' or creds.get('app_key') != 'stale'
        LongbridgeService.set_credentials(None)

    asyncio.run(_run())


def test_save_syncs_sibling_same_app_key_only() -> None:
    """admin=1 与 lustone=101 共享 app_key 时同步 token；乐文 100 不同 key 不拷贝。"""
    store = {
        1: _row(
            id=1,
            user_id=1,
            app_key='shared-key',
            app_secret='old-admin-secret',
            access_token='old-admin-token',
            auto_trade_enabled='0',
            region='cn',
        ),
        101: _row(
            id=2,
            user_id=101,
            app_key='shared-key',
            app_secret='old-lustone-secret',
            access_token='old-lustone-token',
            auto_trade_enabled='1',
            region='cn',
        ),
        100: _row(
            id=3,
            user_id=100,
            app_key='lewen-key',
            app_secret='lewen-secret',
            access_token='lewen-token',
            auto_trade_enabled='1',
            region='cn',
        ),
    }
    saved_rows: list[dict] = []

    async def fake_get(_db, user_id=None):
        return store.get(int(user_id if user_id is not None else ADMIN_LONGBRIDGE_USER_ID))

    async def fake_save(_db, config, user_id=None):
        uid = int(user_id if user_id is not None else config['user_id'])
        saved_rows.append({**config, 'resolved_user_id': uid})
        row = store[uid]
        for key, value in config.items():
            if key == 'id':
                continue
            setattr(row, key, value)
        return row

    async def fake_list_by_app_key(_db, app_key):
        return [row for row in store.values() if row.app_key == app_key]

    async def _run() -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        payload = QuantLongbridgeConfigModel(
            userId=101,
            appKey='shared-key',
            appSecret='new-secret',
            accessToken='new-token',
            region='hk',
        )
        with (
            patch.object(QuantLongbridgeConfigDao, 'get_config', fake_get),
            patch.object(QuantLongbridgeConfigDao, 'save_config', fake_save),
            patch.object(QuantLongbridgeConfigDao, 'list_by_app_key', fake_list_by_app_key),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(LongbridgeBreaker, 'clear_persisted', AsyncMock()),
            patch.object(LongbridgeBreaker, 'bump_creds_epoch', AsyncMock(return_value=2)),
            patch('module_quant.service.quant_service.CryptoUtil.encrypt', side_effect=lambda v: f'enc({v})'),
        ):
            result = await QuantService.save_longbridge_config_services(db, payload, user_id=101)
        assert result.is_success is True
        saved_users = {int(row['resolved_user_id']) for row in saved_rows}
        assert saved_users == {101, 1}
        assert 100 not in saved_users
        lustone = next(row for row in saved_rows if int(row['resolved_user_id']) == 101)
        admin = next(row for row in saved_rows if int(row['resolved_user_id']) == 1)
        assert lustone['access_token'] == 'enc(new-token)'
        assert lustone['app_secret'] == 'enc(new-secret)'
        assert admin['access_token'] == lustone['access_token']
        assert admin['app_secret'] == lustone['app_secret']
        assert admin['region'] == 'hk'
        assert 'auto_trade_enabled' not in admin
        assert store[1].auto_trade_enabled == '0'
        assert store[101].auto_trade_enabled == '1'
        assert store[100].access_token == 'lewen-token'
        assert store[100].app_key == 'lewen-key'

    asyncio.run(_run())


def test_save_same_token_clears_process_cut_off() -> None:
    """保存（含脱敏重存）后本进程切断必须解除，并 bump epoch。"""
    store = {
        101: _row(
            id=2,
            user_id=101,
            app_key='shared-key',
            app_secret='stored-secret',
            access_token='stored-token',
            auto_trade_enabled='1',
        )
    }

    async def fake_get(_db, user_id=None):
        return store.get(int(user_id))

    async def fake_save(_db, config, user_id=None):
        return store[101]

    async def _run() -> None:
        LongbridgeService._reset_auth_breaker()
        LongbridgeService._auth_cut_off = True
        LongbridgeService._auth_cut_off_sig = 'same'
        LongbridgeBreaker.trip('unauthorized', 60)
        db = MagicMock()
        db.commit = AsyncMock()
        payload = QuantLongbridgeConfigModel(
            userId=101,
            appKey='shared-key',
            appSecret='****cret',
            accessToken='****oken',
            region='cn',
        )
        with (
            patch.object(QuantLongbridgeConfigDao, 'get_config', fake_get),
            patch.object(QuantLongbridgeConfigDao, 'save_config', fake_save),
            patch.object(QuantLongbridgeConfigDao, 'list_by_app_key', AsyncMock(return_value=[store[101]])),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(LongbridgeBreaker, 'clear_persisted', AsyncMock()) as clear_mock,
            patch.object(LongbridgeBreaker, 'bump_creds_epoch', AsyncMock(return_value=9)) as bump_mock,
        ):
            result = await QuantService.save_longbridge_config_services(db, payload, user_id=101)
        assert result.is_success is True
        assert LongbridgeService._auth_cut_off is False
        assert LongbridgeBreaker.allow() is True
        clear_mock.assert_awaited()
        bump_mock.assert_awaited()

    try:
        asyncio.run(_run())
    finally:
        LongbridgeService._reset_auth_breaker()
        LongbridgeBreaker.reset()
        LongbridgeBreaker._seen_creds_epoch = 0
        LongbridgeBreaker._cached_remote_epoch = 0
