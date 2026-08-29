"""WebSocket 鉴权：JWT 签名 + Redis 会话一致性。

HTTP 登录把令牌写入 `access_token:{session_id}`（允许多端）或
`access_token:{user_id}`（单端互斥）。WS 必须同样核对 Redis，避免仅校验
签名的已注销 / 被踢下线令牌继续推送。Redis 客户端缺失时失败关闭。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import jwt

from common.enums import RedisInitKeyConfig
from config.env import AppConfig, JwtConfig
from config.get_redis import RedisUtil

if TYPE_CHECKING:
    from fastapi import WebSocket


def verify_token(token: str | None) -> bool:
    """仅校验签名与有效期（exp），不做会话级校验。"""
    if not token:
        return False
    try:
        jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
        return True
    except Exception:
        return False


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8')
    return str(value)


def _session_redis_key(payload: dict[str, Any]) -> str | None:
    user_id = payload.get('user_id')
    if user_id is None or str(user_id).strip() == '':
        return None
    if AppConfig.app_same_time_login:
        session_id = payload.get('session_id')
        if session_id is None or str(session_id).strip() == '':
            return None
        return f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}'
    try:
        return f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{int(user_id)}'
    except (TypeError, ValueError):
        return None


async def verify_ws_session(token: str | None) -> bool:
    """JWT 合法且 Redis 会话令牌与当前 token 一致。Redis 缺失则失败关闭。"""
    if not token:
        return False
    try:
        payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    key = _session_redis_key(payload)
    if not key:
        return False
    redis = RedisUtil.get_client()
    if redis is None:
        return False
    try:
        redis_token = _as_text(await redis.get(key))
    except Exception:
        return False
    return token == redis_token


def token_from_websocket(websocket: WebSocket, query_token: str | None = None) -> str | None:
    """只读 Cookie。query token 已下线，避免 JWT 进代理日志。"""
    del query_token
    if not websocket.cookies:
        return None
    return websocket.cookies.get('Admin-Token')


def token_from_auth_frame(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get('type') != 'auth':
        return None
    token = data.get('token')
    return str(token) if token else None


async def authorize_websocket(websocket: WebSocket, query_token: str | None = None) -> bool:
    """Cookie Admin-Token 优先，否则等开帧 `{type:auth,token}`，再核 Redis 会话。"""
    cookie_token = token_from_websocket(websocket, query_token)
    if cookie_token:
        return await verify_ws_session(cookie_token)
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
    except Exception:
        return False
    return await verify_ws_session(token_from_auth_frame(raw))
