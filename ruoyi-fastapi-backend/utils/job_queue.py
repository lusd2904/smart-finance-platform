"""
Redis 列表队列：把长任务从 APScheduler 线程里卸下来。

调度任务优先入队；Redis 不可用时返回 False，由调用方同步执行兜底。
不引入 Celery，复用现有 Redis 连接。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from utils.log_util import logger

QUEUE_KEY = 'sfp:job:queue'
KNOWN_JOBS = frozenset(
    {
        'market_sync',
        'factor_scan',
        'factor_qc',
        'sentiment_collect',
        'watchlist_analyze',
        'indicator_refresh',
        'market_review',
    }
)


class JobQueue:
    @classmethod
    def _redis(cls):
        try:
            from config.get_redis import RedisUtil

            return RedisUtil.get_client()
        except Exception:
            return None

    @classmethod
    def encode(cls, job_type: str, payload: dict[str, Any] | None = None) -> str:
        job_type = str(job_type or '').strip()
        if job_type not in KNOWN_JOBS:
            raise ValueError(f'未知任务类型: {job_type}')
        return json.dumps(
            {
                'type': job_type,
                'payload': payload or {},
                'enqueuedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            ensure_ascii=False,
            default=str,
        )

    @classmethod
    def decode(cls, raw: Any) -> dict[str, Any] | None:
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            data = json.loads(raw)
        except Exception:
            return None
        if not isinstance(data, dict) or data.get('type') not in KNOWN_JOBS:
            return None
        return data

    @classmethod
    async def enqueue(cls, job_type: str, payload: dict[str, Any] | None = None) -> bool:
        redis = cls._redis()
        if redis is None:
            return False
        try:
            await redis.lpush(QUEUE_KEY, cls.encode(job_type, payload))
            return True
        except Exception as exc:
            logger.warning(f'[job-queue] 入队失败 {job_type}: {exc}')
            return False

    @classmethod
    async def dispatch(cls, job: dict[str, Any]) -> Any:
        job_type = job.get('type')
        payload = job.get('payload') or {}
        handler = HANDLERS.get(job_type)
        if not handler:
            raise ValueError(f'无处理器: {job_type}')
        return await handler(payload)

    @classmethod
    async def consume_forever(cls, stop_event: asyncio.Event) -> None:
        logger.info('[job-queue] worker 已启动')
        while not stop_event.is_set():
            redis = cls._redis()
            if redis is None:
                await asyncio.sleep(1)
                continue
            try:
                item = await redis.brpop(QUEUE_KEY, timeout=2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f'[job-queue] brpop 失败: {exc}')
                await asyncio.sleep(1)
                continue
            if not item:
                continue
            _key, raw = item
            job = cls.decode(raw)
            if not job:
                logger.warning('[job-queue] 丢弃无法解析的任务')
                continue
            try:
                result = await cls.dispatch(job)
                logger.info(f'[job-queue] {job.get("type")} 完成: {str(result)[:240]}')
            except Exception as exc:
                logger.error(f'[job-queue] {job.get("type")} 失败: {exc}')
        logger.info('[job-queue] worker 已停止')


async def _market_sync(payload: dict[str, Any]) -> dict[str, Any]:
    from module_market.service.sync_service import MarketSyncService

    years = int(payload.get('years') or 10)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, MarketSyncService.sync, None, years)


async def _factor_scan(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.snapshot_service import SnapshotService

    profile = str(payload.get('profile') or 'balanced')
    async with AsyncSessionLocal() as db:
        return await SnapshotService.run_daily_factor_scan(db, profile=profile)


async def _factor_qc(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.factor_qc_service import FactorQcService

    market = str(payload.get('market') or 'US')
    async with AsyncSessionLocal() as db:
        return await FactorQcService.run_and_store(db, market=market)


async def _sentiment_collect(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_sentiment.service.sentiment_service import SentimentService

    async with AsyncSessionLocal() as db:
        if payload.get('analyze'):
            return await SentimentService.collect_and_analyze_services(db)
        return await SentimentService.collect_news_services(db)


async def _watchlist_analyze(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.watchlist_service import MarketWatchlistService

    async with AsyncSessionLocal() as db:
        return await MarketWatchlistService.run_hourly_job(db)


async def _indicator_refresh(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.snapshot_service import SnapshotService

    async with AsyncSessionLocal() as db:
        return await SnapshotService.run_indicator_refresh(db)


async def _market_review(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.market_review_service import MarketReviewService

    markets = payload.get('markets')
    async with AsyncSessionLocal() as db:
        return await MarketReviewService.analyze_markets(db, markets)


HANDLERS = {
    'market_sync': _market_sync,
    'factor_scan': _factor_scan,
    'factor_qc': _factor_qc,
    'sentiment_collect': _sentiment_collect,
    'watchlist_analyze': _watchlist_analyze,
    'indicator_refresh': _indicator_refresh,
    'market_review': _market_review,
}
