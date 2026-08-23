import asyncio

from apscheduler.events import EVENT_ALL
from redis import asyncio as aioredis

from common.constant import LockConstant
from config.env import AppConfig, LogConfig
from config.providers import get_scheduler_persistence
from config.scheduler.jobstores import scheduler
from utils.log_util import logger
from utils.server_util import StartupUtil, WorkerIdUtil


class LeaderElectionMixin:
    """
    基于 Redis 锁的调度 Leader 选举与锁生命周期管理
    """

    # 分布式锁相关类变量
    _is_leader: bool = False
    _worker_id: str = WorkerIdUtil.get_worker_id(LogConfig.log_worker_id)
    _redis: aioredis.Redis | None = None
    _lock_renewal_task: asyncio.Task | None = None
    _lock_lost_task: asyncio.Task | None = None
    _reacquire_task: asyncio.Task | None = None
    _reacquire_interval_seconds: float = 5.0

    @classmethod
    def bind_redis(cls, redis: aioredis.Redis) -> None:
        """
        绑定 Redis，供非 Leader 的 API 进程发布同步/执行命令
        """
        cls._redis = redis

    @classmethod
    def is_leader(cls) -> bool:
        return cls._is_leader

    @classmethod
    def _should_enable_scheduler_sync(cls) -> bool:
        """
        判断是否需要启用任务状态同步机制

        独立调度进程必须监听 API 的配置变更；多 worker 的 all 模式也需要。
        """
        if AppConfig.app_role == 'scheduler':
            return True
        return not AppConfig.app_reload and AppConfig.app_workers > 1

    @classmethod
    async def init_system_scheduler(cls, redis: aioredis.Redis) -> None:
        """
        应用启动时初始化定时任务（使用独立调度锁，避免与 API 进程抢同一把锁）

        :param redis: Redis连接对象
        :return:
        """
        cls._redis = redis
        logger.info(f'🔎 Worker {cls._worker_id} 尝试获取 Scheduler 锁...')

        acquired = await StartupUtil.acquire_startup_log_gate(
            redis=redis,
            lock_key=LockConstant.SCHEDULER_LOCK_KEY,
            worker_id=cls._worker_id,
            lock_expire_seconds=LockConstant.LOCK_EXPIRE_SECONDS,
        )

        if acquired:
            await cls._start_scheduler_as_leader(redis)
        else:
            cls._is_leader = False
            logger.info(f'⏸️ Worker {cls._worker_id} 未持有 Scheduler 锁，跳过 Scheduler 启动')

    @classmethod
    async def _start_scheduler_as_leader(cls, redis: aioredis.Redis) -> None:
        """
        以 Leader 身份启动 Scheduler（内部方法，调用前需确保已持有锁）

        :param redis: Redis连接对象
        :return: None
        """
        cls._is_leader = True
        cls._disposed_sync_engines = False
        logger.info(f'🎯 Worker {cls._worker_id} 持有 Scheduler 锁，开始启动定时任务...')
        # 注册任务模块（module_task.*），确保调度调用目标可被动态解析
        import module_task  # noqa: F401

        # 懒加载配置 scheduler
        cls._configure_scheduler()
        scheduler.start()

        # 加载数据库中的定时任务
        persistence = get_scheduler_persistence()
        async with cls._get_sync_async_session() as session:
            job_list = await persistence.get_jobs_for_scheduler(session)
            for item in job_list:
                cls._add_job_to_scheduler(item)

        # 添加事件监听器
        scheduler.add_listener(cls.scheduler_event_listener, EVENT_ALL)

        cls._lock_renewal_task = StartupUtil.start_lock_renewal(
            redis=redis,
            lock_key=LockConstant.SCHEDULER_LOCK_KEY,
            worker_id=cls._worker_id,
            lock_expire_seconds=LockConstant.LOCK_EXPIRE_SECONDS,
            interval_seconds=LockConstant.LOCK_RENEWAL_INTERVAL,
            on_lock_lost=cls.on_lock_lost,
        )
        cls._command_listener_task = asyncio.create_task(cls._listen_command_channel(redis))
        scheduler.add_job(
            func=cls.publish_heartbeat,
            trigger='interval',
            seconds=8,
            id='_scheduler_heartbeat',
            name='Scheduler心跳',
            replace_existing=True,
        )
        await cls.publish_heartbeat()

        if cls._should_enable_scheduler_sync():
            # 添加任务状态同步任务（每30秒从数据库同步一次任务状态）
            scheduler.add_job(
                func=cls.request_scheduler_sync,
                trigger='interval',
                seconds=30,
                id='_scheduler_job_sync',
                name='Scheduler任务同步',
                replace_existing=True,
            )
            cls._sync_listener_task = asyncio.create_task(cls._listen_sync_channel(redis))

        logger.info('✅️ 系统初始定时任务加载成功')

    @classmethod
    def on_lock_lost(cls) -> None:
        """
        锁丢失处理入口

        :return: None
        """
        if not cls._is_leader:
            return
        cls._is_leader = False
        logger.warning(f'⚠️ Worker {cls._worker_id} 失去 Scheduler 锁')
        if cls._lock_lost_task:
            cls._lock_lost_task.cancel()
        cls._lock_lost_task = asyncio.create_task(cls._handle_lock_lost())

    @classmethod
    async def _cancel_task(cls, task: asyncio.Task | None) -> None:
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @classmethod
    async def _stop_leader_aux_tasks(cls) -> None:
        await cls._cancel_task(cls._sync_listener_task)
        cls._sync_listener_task = None
        await cls._cancel_task(cls._command_listener_task)
        cls._command_listener_task = None
        await cls._cancel_task(cls._lock_renewal_task)
        cls._lock_renewal_task = None
        await cls._cancel_task(cls._sync_task)
        cls._sync_task = None
        cls._sync_pending = False

    @classmethod
    async def _handle_lock_lost(cls) -> None:
        """
        处理锁丢失后的资源释放

        :return: None
        """
        await cls._stop_leader_aux_tasks()
        if getattr(scheduler, 'running', False):
            scheduler.shutdown()
        await cls._dispose_sync_async_engine()
        cls._dispose_sync_engines()
        cls._ensure_reacquire_task()

    @classmethod
    def _ensure_reacquire_task(cls) -> None:
        """
        启动锁重新竞争任务

        :return: None
        """
        if not cls._redis:
            return
        if cls._reacquire_task and not cls._reacquire_task.done():
            return
        cls._reacquire_task = asyncio.create_task(cls._run_reacquire_loop())

    @classmethod
    async def _run_reacquire_loop(cls) -> None:
        """
        循环尝试重新获取锁并恢复调度器

        :return: None
        """
        try:
            while not cls._is_leader:
                if not cls._redis:
                    await asyncio.sleep(cls._reacquire_interval_seconds)
                    continue
                acquired = await StartupUtil.acquire_startup_log_gate(
                    redis=cls._redis,
                    lock_key=LockConstant.SCHEDULER_LOCK_KEY,
                    worker_id=cls._worker_id,
                    lock_expire_seconds=LockConstant.LOCK_EXPIRE_SECONDS,
                )
                if acquired:
                    # 直接调用 _start_scheduler_as_leader，避免重复获取锁
                    await cls._start_scheduler_as_leader(cls._redis)
                    return
                await asyncio.sleep(cls._reacquire_interval_seconds)
        except asyncio.CancelledError:
            raise
        finally:
            cls._reacquire_task = None

    @classmethod
    async def close_system_scheduler(cls) -> None:
        """
        应用关闭时关闭定时任务

        :return:
        """
        await cls._stop_leader_aux_tasks()
        if cls._reacquire_task:
            cls._reacquire_task.cancel()
            try:
                await cls._reacquire_task
            except asyncio.CancelledError:
                pass
            cls._reacquire_task = None
        await cls._dispose_sync_async_engine()
        cls._dispose_sync_engines()
        if cls._lock_lost_task:
            cls._lock_lost_task.cancel()
            try:
                await cls._lock_lost_task
            except asyncio.CancelledError:
                pass
            cls._lock_lost_task = None
        if getattr(scheduler, 'running', False):
            scheduler.shutdown()
            logger.info('✅️ 关闭定时任务成功')
        # 释放调度锁
        if cls._redis:
            current_holder = await cls._redis.get(LockConstant.SCHEDULER_LOCK_KEY)
            if current_holder == cls._worker_id:
                await cls._redis.delete(LockConstant.SCHEDULER_LOCK_KEY)
                logger.info(f'🔓 Worker {cls._worker_id} 释放 Scheduler 锁')
