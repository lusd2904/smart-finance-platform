"""对外 Widget / 需求清单：用户名密码换短期 JWT。"""

import asyncio
import os
import sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.exception import AuthException, ServiceException
from module_admin.service.login_service import LoginService
from module_admin.service.open_access_service import (
    OPEN_AUD,
    OPEN_SCOPE,
    OPEN_TTL_MINUTES,
    OpenAccessService,
    decode_open_token,
    extract_bearer_token,
)


def _run(coro):
    return asyncio.run(coro)


def test_extract_bearer_requires_header() -> None:
    try:
        extract_bearer_token(None)
    except AuthException as exc:
        assert '获取令牌' in exc.message
    else:
        raise AssertionError('缺 Header 应失败')


def test_extract_bearer_rejects_empty_bearer() -> None:
    try:
        extract_bearer_token('Bearer ')
    except AuthException:
        return
    raise AssertionError('空 Bearer 应失败')


def test_issue_token_requires_credentials() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    try:
        _run(OpenAccessService.issue_token(request, SimpleNamespace(), '', 'x'))
    except ServiceException as exc:
        assert '用户名或密码' in exc.message
    else:
        raise AssertionError('空用户名应失败')


def test_issue_token_mocked() -> None:
    user = SimpleNamespace(user_id=1, user_name='admin')
    stored: dict[str, str] = {}

    class _Redis:
        async def set(self, key, value, ex=None):
            stored[key] = value

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_Redis())))
    with (
        patch.object(LoginService, 'authenticate_user', AsyncMock(return_value=(user, None))),
        patch.object(LoginService, 'create_access_token', AsyncMock(return_value='open-jwt')),
    ):
        result = _run(OpenAccessService.issue_token(request, SimpleNamespace(), 'admin', 'secret'))
    assert result['token'] == 'open-jwt'
    assert result['tokenType'] == 'Bearer'
    assert result['expiresIn'] == OPEN_TTL_MINUTES * 60
    assert any(key.startswith('open_token:') for key in stored)


def test_roundtrip_jwt() -> None:
    user = SimpleNamespace(user_id=7, user_name='alice')
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    with patch.object(LoginService, 'authenticate_user', AsyncMock(return_value=(user, None))):
        issued = _run(OpenAccessService.issue_token(request, SimpleNamespace(), 'alice', 'pw'))
    payload = decode_open_token(f'Bearer {issued["token"]}')
    assert payload['user_name'] == 'alice'
    assert payload['scope'] == OPEN_SCOPE
    assert payload['aud'] == OPEN_AUD
    verified = _run(OpenAccessService.verify_bearer(request, f'Bearer {issued["token"]}'))
    assert verified['user_id'] == '7'


def test_verify_rejects_sync_token() -> None:
    sync_claims = {
        'user_id': '1',
        'user_name': 'admin',
        'session_id': 'x',
        'scope': 'sync',
        'aud': 'open-sync',
    }
    token = _run(LoginService.create_access_token(data=sync_claims, expires_delta=timedelta(minutes=10)))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    try:
        _run(OpenAccessService.verify_bearer(request, f'Bearer {token}'))
    except AuthException:
        return
    raise AssertionError('sync JWT 不能访问对外只读接口')
