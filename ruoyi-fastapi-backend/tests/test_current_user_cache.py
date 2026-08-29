import os
import sys
from datetime import timedelta

import pytest

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from common.entity.vo.user_vo import CurrentUserModel, UserInfoModel
from module_admin.service.login_service import LoginService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: timedelta | None = None):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)

    async def incr(self, key: str) -> int:
        n = int(self.store.get(key) or 0) + 1
        self.store[key] = str(n)
        return n


def _user() -> CurrentUserModel:
    return CurrentUserModel(
        permissions=['*:*:*'],
        roles=['admin'],
        user=UserInfoModel(user_id=1, user_name='admin', nick_name='管理员'),
        is_default_modify_pwd=False,
        is_password_expired=False,
    )


@pytest.mark.asyncio
async def test_current_user_cache_roundtrip() -> None:
    redis = FakeRedis()
    model = _user()
    await LoginService.cache_current_user(redis, 1, model)
    loaded = await LoginService.load_cached_current_user(redis, 1)
    assert loaded is not None
    assert loaded.user.user_id == 1
    assert loaded.roles == ['admin']
    assert loaded.permissions == ['*:*:*']


@pytest.mark.asyncio
async def test_current_user_cache_epoch_invalidates() -> None:
    redis = FakeRedis()
    await LoginService.cache_current_user(redis, 1, _user())
    redis.store['current_user_epoch'] = '9'
    loaded = await LoginService.load_cached_current_user(redis, 1)
    assert loaded is None


@pytest.mark.asyncio
async def test_current_user_cache_delete() -> None:
    redis = FakeRedis()
    await LoginService.cache_current_user(redis, 7, _user())
    await redis.delete(LoginService._current_user_cache_key(7))
    assert await LoginService.load_cached_current_user(redis, 7) is None
