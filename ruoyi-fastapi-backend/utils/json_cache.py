"""轻量 Redis JSON 缓存，Redis 不可用时静默降级。"""

from __future__ import annotations

import json
from typing import Any

from utils.log_util import logger


def _redis():
    try:
        from config.get_redis import RedisUtil

        return RedisUtil.get_client()
    except Exception:
        return None


async def cache_get_json(key: str) -> Any | None:
    redis = _redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug(f'[cache] get {key} 失败: {exc}')
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    redis = _redis()
    if redis is None:
        return
    try:
        await redis.setex(key, int(ttl_seconds), json.dumps(value, default=str, ensure_ascii=False))
    except Exception as exc:
        logger.debug(f'[cache] set {key} 失败: {exc}')
