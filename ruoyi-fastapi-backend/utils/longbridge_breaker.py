"""
长桥调用熔断。

401004 / 凭证失效立即开闸；超时累计后开闸。开闸期间所有进程不再打长桥。
禁止自动 refresh token。
"""

from __future__ import annotations

import time
from typing import Any

from utils.log_util import logger

REDIS_KEY = 'sfp:lb:circuit'
OPEN_SECONDS_AUTH = 300
OPEN_SECONDS_TIMEOUT = 120
TIMEOUT_FAILS_TO_OPEN = 2
TIMEOUT_WINDOW_SECONDS = 30


def is_auth_failure(exc: BaseException | str | None) -> bool:
    text = str(exc or '')
    lowered = text.lower()
    if '401004' in text:
        return True
    if '401' in text and ('unauth' in lowered or 'token' in lowered or 'access' in lowered):
        return True
    if 'unauthorized' in lowered or 'unauth' in lowered:
        return True
    if 'token' in lowered and any(word in lowered for word in ('invalid', 'expired', '失效', '过期')):
        return True
    if '凭证失效' in text or '令牌无效' in text:
        return True
    return False


def is_timeout_failure(exc: BaseException | str | None) -> bool:
    text = str(exc or '').lower()
    return any(token in text for token in ('timeout', 'timed out', 'time out', 'deadline', '超时'))


class LongbridgeBreaker:
    _open_until: float = 0.0
    _reason: str = ''
    _timeout_fails: list[float] = []

    @classmethod
    def reset(cls) -> None:
        cls._open_until = 0.0
        cls._reason = ''
        cls._timeout_fails = []

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        open_now = not cls.allow()
        remaining = max(0, int(cls._open_until - time.monotonic())) if open_now else 0
        return {
            'open': open_now,
            'reason': cls._reason if open_now else '',
            'remainingSeconds': remaining,
        }

    @classmethod
    def allow(cls) -> bool:
        if cls._open_until and time.monotonic() < cls._open_until:
            return False
        if cls._open_until and time.monotonic() >= cls._open_until:
            cls._open_until = 0.0
            cls._reason = ''
        return True

    @classmethod
    def trip(cls, reason: str, seconds: int) -> None:
        until = time.monotonic() + max(5, int(seconds))
        if until > cls._open_until:
            cls._open_until = until
            cls._reason = reason
        logger.warning(f'[长桥熔断] 开闸 reason={reason} seconds={seconds}，期间不再请求长桥')
        cls._persist_open(reason, seconds)

    @classmethod
    def record_success(cls) -> None:
        cls._timeout_fails = []

    @classmethod
    def record_failure(cls, exc: BaseException | str | None) -> None:
        if is_auth_failure(exc):
            cls.trip('unauthorized', OPEN_SECONDS_AUTH)
            return
        if is_timeout_failure(exc):
            now = time.monotonic()
            cls._timeout_fails = [ts for ts in cls._timeout_fails if now - ts <= TIMEOUT_WINDOW_SECONDS]
            cls._timeout_fails.append(now)
            if len(cls._timeout_fails) >= TIMEOUT_FAILS_TO_OPEN:
                cls.trip('timeout', OPEN_SECONDS_TIMEOUT)

    @classmethod
    def blocked_message(cls) -> str:
        reason = cls._reason or 'circuit_open'
        if reason == 'unauthorized':
            return '长桥凭证失效，熔断中，已停止请求（不会自动刷新 token）'
        if reason == 'timeout':
            return '长桥超时熔断中，已停止请求'
        return '长桥熔断中，暂不请求行情'

    @classmethod
    def _persist_open(cls, reason: str, seconds: int) -> None:
        try:
            from config.get_redis import RedisUtil

            redis = RedisUtil.get_client()
        except Exception:
            return
        if redis is None:
            return
        payload = f'{reason}|{int(time.time()) + int(seconds)}'
        try:
            maybe = redis.setex(REDIS_KEY, int(seconds), payload)
            if hasattr(maybe, '__await__'):
                return
        except Exception:
            return

    @classmethod
    async def hydrate_from_redis(cls) -> None:
        try:
            from config.get_redis import RedisUtil

            redis = RedisUtil.get_client()
        except Exception:
            return
        if redis is None:
            return
        try:
            raw = await redis.get(REDIS_KEY)
        except Exception:
            return
        if not raw:
            return
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            reason, until_s = str(raw).split('|', 1)
            remaining = int(until_s) - int(time.time())
        except (TypeError, ValueError):
            return
        if remaining > 0:
            cls._open_until = time.monotonic() + remaining
            cls._reason = reason
