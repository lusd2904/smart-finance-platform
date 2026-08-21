"""请求审计：方法、路径、状态码、耗时、用户，不记录请求体以免泄露密钥。"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from common.context import current_user
from utils.log_util import logger

_SKIP_PREFIXES = (
    '/metrics',
    '/docs',
    '/redoc',
    '/openapi.json',
    '/favicon.ico',
    '/assets/',
    '/static/',
)


def _user_id() -> str:
    try:
        user = current_user.get()
    except Exception:
        user = None
    if not user:
        return '-'
    inner = getattr(user, 'user', None)
    uid = getattr(inner, 'user_id', None) if inner is not None else getattr(user, 'user_id', None)
    return str(uid) if uid is not None else '-'


def _should_skip(path: str) -> bool:
    candidates = {path}
    if path.startswith('/docker-api'):
        candidates.add(path[len('/docker-api'):] or '/')
    for candidate in candidates:
        if any(candidate == prefix or candidate.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return True
    return False


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if _should_skip(path):
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f'[audit] {request.method} {path} status={response.status_code} '
            f'user={_user_id()} {elapsed_ms:.0f}ms'
        )
        return response


def add_audit_middleware(app: FastAPI) -> None:
    app.add_middleware(AuditMiddleware)
