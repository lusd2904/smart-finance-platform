"""
分析调度微服务的 Redis 控制面：心跳、立即执行、配置同步。

平台 API 只写库并投递命令，真正跑任务的是独立 scheduler 进程。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from common.constant import SchedulerConstant
from config.get_redis import RedisUtil
from utils.log_util import logger


class SchedulerRuntime:
    @staticmethod
    def _redis() -> Any:
        try:
            return RedisUtil.get_client()
        except Exception:
            return None

    @classmethod
    async def publish(cls, payload: dict[str, Any]) -> bool:
        redis = cls._redis()
        if redis is None:
            return False
        try:
            await redis.publish(SchedulerConstant.COMMAND_CHANNEL, json.dumps(payload, ensure_ascii=False, default=str))
            return True
        except Exception as exc:
            logger.warning(f'[scheduler-runtime] 发布命令失败: {exc}')
            return False

    @classmethod
    async def publish_run(cls, job_id: int) -> bool:
        return await cls.publish({'action': 'run', 'jobId': int(job_id)})

    @classmethod
    async def publish_sync(cls) -> bool:
        return await cls.publish({'action': 'sync'})

    @classmethod
    async def write_heartbeat(cls, payload: dict[str, Any]) -> None:
        redis = cls._redis()
        if redis is None:
            return
        body = dict(payload)
        body.setdefault('alive', True)
        body.setdefault('ts', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        try:
            await redis.set(
                SchedulerConstant.HEARTBEAT_KEY,
                json.dumps(body, ensure_ascii=False, default=str),
                ex=SchedulerConstant.HEARTBEAT_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning(f'[scheduler-runtime] 写心跳失败: {exc}')

    @classmethod
    async def read_heartbeat(cls) -> dict[str, Any] | None:
        redis = cls._redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(SchedulerConstant.HEARTBEAT_KEY)
        except Exception as exc:
            logger.warning(f'[scheduler-runtime] 读心跳失败: {exc}')
            return None
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    def is_alive(cls, heartbeat: dict[str, Any] | None) -> bool:
        return bool(heartbeat and heartbeat.get('alive'))
