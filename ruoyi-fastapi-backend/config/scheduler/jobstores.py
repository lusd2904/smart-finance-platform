from typing import Any

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from config.database import (
    SYNC_SQLALCHEMY_DATABASE_URL,
    create_async_db_engine,
    create_async_session_local,
    create_sync_db_engine,
    create_sync_session_local,
)
from config.env import RedisConfig

redis_config = {
    'host': RedisConfig.redis_host,
    'port': RedisConfig.redis_port,
    'username': RedisConfig.redis_username,
    'password': RedisConfig.redis_password,
    'db': RedisConfig.redis_database,
}
job_defaults = {'coalesce': False, 'max_instance': 1}
scheduler = AsyncIOScheduler()


class SchedulerEngineMixin:
    """
    调度器引擎与 jobstore 相关的懒加载资源管理
    """

    # 懒加载的同步 Engine 和 SessionLocal
    _jobstore_engine: Engine | None = None
    _listener_engine: Engine | None = None
    _session_local: Any | None = None
    _scheduler_configured: bool = False

    # 同步任务使用的异步引擎与会话工厂
    _sync_async_engine: AsyncEngine | None = None
    _sync_async_sessionmaker: Any | None = None
    _disposed_sync_engines: bool = False

    @classmethod
    def _get_jobstore_engine(cls) -> Engine:
        """
        懒加载获取 jobstore 使用的同步 Engine

        :return: 同步 Engine
        """
        if cls._jobstore_engine is None:
            cls._jobstore_engine = create_sync_db_engine(echo=False)
        return cls._jobstore_engine

    @classmethod
    def _get_listener_engine(cls) -> Engine:
        """
        懒加载获取 listener 使用的同步 Engine

        :return: 同步 Engine
        """
        if cls._listener_engine is None:
            cls._listener_engine = create_sync_db_engine()
        return cls._listener_engine

    @classmethod
    def _get_session_local(cls) -> Any:
        """
        懒加载获取同步 SessionLocal

        :return: SessionLocal
        """
        if cls._session_local is None:
            cls._session_local = create_sync_session_local(cls._get_listener_engine())
        return cls._session_local

    @classmethod
    def _configure_scheduler(cls) -> None:
        """
        配置 scheduler（懒加载 jobstore）

        :return: None
        """
        if cls._scheduler_configured:
            return
        job_stores = {
            'default': MemoryJobStore(),
            'sqlalchemy': SQLAlchemyJobStore(url=SYNC_SQLALCHEMY_DATABASE_URL, engine=cls._get_jobstore_engine()),
            'redis': RedisJobStore(**redis_config),
        }
        executors = {'default': AsyncIOExecutor(), 'processpool': ProcessPoolExecutor(2)}
        scheduler.configure(jobstores=job_stores, executors=executors, job_defaults=job_defaults)
        cls._scheduler_configured = True

    @classmethod
    def _get_sync_async_session(cls) -> Any:
        """
        获取同步任务使用的异步 Session

        :return: 异步 Session
        """
        if not cls._sync_async_sessionmaker:
            cls._sync_async_engine = create_async_db_engine(echo=False)
            cls._sync_async_sessionmaker = create_async_session_local(cls._sync_async_engine)
        return cls._sync_async_sessionmaker()

    @classmethod
    async def _dispose_sync_async_engine(cls) -> None:
        """
        释放同步任务使用的异步 Engine

        :return: None
        """
        if cls._sync_async_engine:
            await cls._sync_async_engine.dispose()
            cls._sync_async_engine = None
            cls._sync_async_sessionmaker = None

    @classmethod
    def _dispose_sync_engines(cls) -> None:
        """
        释放 Scheduler 使用的同步 Engine

        :return: None
        """
        if cls._disposed_sync_engines:
            return
        if cls._jobstore_engine:
            cls._jobstore_engine.dispose()
            cls._jobstore_engine = None
        if cls._listener_engine:
            cls._listener_engine.dispose()
            cls._listener_engine = None
        cls._session_local = None
        cls._disposed_sync_engines = True
