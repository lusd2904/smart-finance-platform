"""
自动分析调度微服务。

只跑 APScheduler + Redis 队列消费，不挂业务 HTTP 路由，避免和平台 API 抢 CPU/内存。
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import Response

from config.env import AppConfig
from config.get_db import close_async_engine, init_create_table
from config.get_redis import RedisUtil
from config.get_scheduler import SchedulerUtil, scheduler
from middlewares.metrics_middleware import render_metrics
from utils.job_queue import JobQueue
from utils.log_util import logger
from utils.scheduler_runtime import SchedulerRuntime


async def _stop_scheduler_runtime(app: FastAPI) -> None:
    stop = getattr(app.state, 'job_queue_stop', None)
    if stop:
        stop.set()
    job_task = getattr(app.state, 'job_queue_task', None)
    if job_task:
        job_task.cancel()
        try:
            await job_task
        except asyncio.CancelledError:
            pass
    lock_task = getattr(app.state, 'lock_renewal_task', None)
    if lock_task:
        lock_task.cancel()
        try:
            await lock_task
        except asyncio.CancelledError:
            pass
    await RedisUtil.close_redis_pool(app)
    await SchedulerUtil.close_system_scheduler()
    await close_async_engine()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state._start_time = time.time()
    app.state.redis = await RedisUtil.create_redis_pool(log_enabled=True)
    logger.info(f'⏰️ 分析调度微服务启动 role={AppConfig.app_role} worker={SchedulerUtil._worker_id}')
    await init_create_table()
    await RedisUtil.check_redis_connection(app.state.redis, log_enabled=True)
    await RedisUtil.init_sys_dict(app.state.redis)
    await RedisUtil.init_sys_config(app.state.redis)
    from utils.longbridge_breaker import LongbridgeBreaker

    await LongbridgeBreaker.hydrate_from_redis()
    if AppConfig.runs_scheduler():
        await SchedulerUtil.init_system_scheduler(app.state.redis)
    else:
        logger.info(f'⏸️ APP_ROLE={AppConfig.app_role}，本进程不跑 APScheduler')
    if AppConfig.runs_job_queue_worker():
        app.state.job_queue_stop = asyncio.Event()
        app.state.job_queue_task = asyncio.create_task(
            JobQueue.consume_forever(app.state.job_queue_stop, AppConfig.app_job_group)
        )
    else:
        app.state.job_queue_stop = None
        app.state.job_queue_task = None
        logger.info('⏸️ 本进程不消费 Redis 任务队列')
    logger.info(
        f'🚀 jobs 进程已就绪 role={AppConfig.app_role} group={AppConfig.app_job_group} '
        f'scheduler={AppConfig.runs_scheduler()} worker={AppConfig.runs_job_queue_worker()}'
    )
    yield
    logger.info('分析调度微服务正在关闭')
    await _stop_scheduler_runtime(app)


def create_scheduler_app() -> FastAPI:
    app = FastAPI(
        title='Analysis Scheduler',
        description='自动分析定时任务微服务',
        version=AppConfig.app_version,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get('/health', summary='健康检查', include_in_schema=False)
    async def health() -> dict[str, Any]:
        heartbeat = await SchedulerRuntime.read_heartbeat()
        from utils.longbridge_breaker import LongbridgeBreaker

        return {
            'status': 'up',
            'role': AppConfig.app_role,
            'jobGroup': AppConfig.app_job_group,
            'leader': SchedulerUtil.is_leader(),
            'schedulerRunning': bool(getattr(scheduler, 'running', False)),
            'queueDepth': await JobQueue.depth(AppConfig.app_job_group),
            'heartbeatAt': (heartbeat or {}).get('ts'),
            'longbridge': LongbridgeBreaker.snapshot(),
        }

    @app.get('/metrics', summary='Prometheus 监控指标', include_in_schema=False)
    async def metrics() -> Response:
        return render_metrics()

    return app
