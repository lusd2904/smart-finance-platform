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


def _row(**kwargs):
    defaults = {
        'id': 1,
        'user_id': ADMIN_LONGBRIDGE_USER_ID,
        'app_key': '',
        'app_secret': '',
        'access_token': '',
        'region': 'cn',
        'update_time': None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_resolve_user_id_prefers_arg_then_admin() -> None:
    assert resolve_longbridge_user_id(7) == 7
    assert peek_request_user_id() is None
    assert resolve_longbridge_user_id(None) == ADMIN_LONGBRIDGE_USER_ID


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
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
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


def test_ensure_credentials_falls_back_to_admin_without_user_context() -> None:
    admin = _row(
        user_id=ADMIN_LONGBRIDGE_USER_ID,
        app_key='admin-app-key',
        app_secret='admin-secret',
        access_token='admin-access-token',
        region='cn',
    )
    seen: list[int | None] = []

    async def fake_get(_db, user_id=None):
        seen.append(user_id)
        if int(user_id or 0) == ADMIN_LONGBRIDGE_USER_ID:
            return admin
        return None

    async def _run() -> None:
        LongbridgeService.set_credentials(None)
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
            other = LongbridgeService.resolve_credentials()
        assert seen == [ADMIN_LONGBRIDGE_USER_ID, 8]
        assert creds['app_key'] == 'admin-app-key'
        assert creds['access_token'] == 'admin-access-token'
        assert creds['source'] == 'db'
        assert creds['user_id'] == str(ADMIN_LONGBRIDGE_USER_ID)
        assert other['source'] != 'db' or other['app_key'] != 'admin-app-key'
        LongbridgeService.set_credentials(None)

    asyncio.run(_run())
