"""对外只读接口：用户名密码换短期 JWT，不再使用环境变量固定 Token。"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import jwt
from jwt.exceptions import InvalidTokenError

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.ext.asyncio import AsyncSession

from config.env import JwtConfig
from exceptions.exception import AuthException, ServiceException
from module_admin.entity.vo.login_vo import UserLogin
from module_admin.service.login_service import LoginService
from utils.log_util import logger

OPEN_AUD = 'open-api'
OPEN_SCOPE = 'open'
OPEN_TTL_MINUTES = 60
OPEN_REDIS_PREFIX = 'open_token'
_BEARER_PARTS = 2


def extract_bearer_token(authorization: str | None) -> str:
    raw = (authorization or '').strip()
    if raw.lower().startswith('bearer'):
        parts = raw.split(None, 1)
        if len(parts) != _BEARER_PARTS or parts[0].lower() != 'bearer' or not parts[1].strip():
            raise AuthException(data='', message='令牌不合法')
        return parts[1].strip()
    if not raw:
        raise AuthException(data='', message='请先用用户名密码获取令牌')
    return raw


def build_open_token_claims(user_id: int | str, user_name: str, session_id: str) -> dict[str, Any]:
    return {
        'user_id': str(user_id),
        'user_name': user_name,
        'session_id': session_id,
        'scope': OPEN_SCOPE,
        'aud': OPEN_AUD,
    }


def decode_open_token(token: str) -> dict[str, Any]:
    raw = extract_bearer_token(token)
    try:
        payload = jwt.decode(
            raw,
            JwtConfig.jwt_secret_key,
            algorithms=[JwtConfig.jwt_algorithm],
            audience=OPEN_AUD,
        )
    except InvalidTokenError as exc:
        logger.warning('对外令牌校验失败')
        raise AuthException(data='', message='令牌已失效，请重新登录') from exc
    if not isinstance(payload, dict) or payload.get('scope') != OPEN_SCOPE or not payload.get('user_id'):
        raise AuthException(data='', message='令牌不合法')
    return payload


class OpenAccessService:
    """Username/password → short-lived JWT for widget dashboard and requirements export."""

    @classmethod
    async def issue_token(
        cls,
        request: Request,
        query_db: AsyncSession,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        user_name = str(username or '').strip()
        if not user_name or not password:
            raise ServiceException(message='用户名或密码不能为空')
        login_user = UserLogin(user_name=user_name, password=password, captcha_enabled=False)
        result = await LoginService.authenticate_user(request, query_db, login_user)
        user = result[0]
        session_id = str(uuid.uuid4())
        claims = build_open_token_claims(user.user_id, user.user_name, session_id)
        access_token = await LoginService.create_access_token(
            data=claims,
            expires_delta=timedelta(minutes=OPEN_TTL_MINUTES),
        )
        redis_client = getattr(getattr(getattr(request, 'app', None), 'state', None), 'redis', None)
        if redis_client is not None:
            await redis_client.set(
                f'{OPEN_REDIS_PREFIX}:{session_id}',
                access_token,
                ex=timedelta(minutes=OPEN_TTL_MINUTES),
            )
        logger.info(f'对外令牌已签发 user={user.user_name}')
        return {
            'token': access_token,
            'expiresIn': OPEN_TTL_MINUTES * 60,
            'tokenType': 'Bearer',
        }

    @classmethod
    async def verify_bearer(cls, request: Request, authorization: str | None) -> dict[str, Any]:
        token = extract_bearer_token(authorization)
        payload = decode_open_token(token)
        session_id = str(payload.get('session_id') or '')
        redis_client = getattr(getattr(getattr(request, 'app', None), 'state', None), 'redis', None)
        if redis_client is not None and session_id:
            stored = await redis_client.get(f'{OPEN_REDIS_PREFIX}:{session_id}')
            if stored is not None:
                stored_text = stored.decode() if isinstance(stored, (bytes, bytearray)) else str(stored)
                if stored_text != token:
                    raise AuthException(data='', message='令牌已失效，请重新登录')
        return payload
