import asyncio
import importlib
import json
from asyncio import iscoroutinefunction
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from apscheduler.job import Job
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.date import DateTrigger

from config.providers import SchedulerJobInfo, get_scheduler_persistence
from config.scheduler.jobstores import scheduler
from config.scheduler.triggers import MyCronTrigger
from utils.log_util import logger
from utils.scheduler_runtime import SchedulerRuntime


class JobCrudMixin:
    """
    调度任务的增删改查、数据库状态同步与执行日志记录
    """

    _job_update_time_cache: dict[str, datetime] = {}
    _sync_channel: str = 'scheduler:sync:request'
    _sync_task: asyncio.Task | None = None
    _sync_pending: bool = False
    _sync_lock: asyncio.Lock = asyncio.Lock()
    _last_sync_at: datetime | None = None
    _sync_debounce_seconds: float = 0.5
    _sync_min_interval_seconds: float = 2.0

    @classmethod
    async def _sync_jobs_from_database(cls) -> None:
        """
        从数据库同步任务状态，确保多worker环境下任务状态一致
        """
        if not cls._is_leader:
            return

        persistence = get_scheduler_persistence()
        try:
            async with cls._get_sync_async_session() as session:
                db_jobs_all = await persistence.get_all_jobs_for_scheduler(session)
                db_jobs_enabled = [job for job in db_jobs_all if job.status == '0']
                db_enabled_ids = {str(job.job_id) for job in db_jobs_enabled}
                db_job_map = {str(job.job_id): job for job in db_jobs_enabled}
                db_job_update_time_map = {
                    str(job.job_id): job.update_time for job in db_jobs_enabled if job.update_time is not None
                }
                scheduler_jobs = scheduler.get_jobs()
                scheduler_job_map = {job.id: job for job in scheduler_jobs if not job.id.startswith('_')}
                scheduler_job_ids = set(scheduler_job_map.keys())

                jobs_to_remove = scheduler_job_ids - db_enabled_ids
                for job_id in jobs_to_remove:
                    scheduler.remove_job(job_id=job_id)
                    logger.info(f'🗑️ 同步移除任务: {job_id}')
                    cls._refresh_job_update_cache(job_id, None)

                jobs_to_add = db_enabled_ids - scheduler_job_ids
                for job_id in jobs_to_add:
                    job_info = db_job_map.get(job_id)
                    if job_info:
                        cls._add_job_to_scheduler(job_info)
                        logger.info(f'➕ 同步添加任务: {job_info.job_name}')
                        cls._refresh_job_update_cache(job_id, job_info.update_time)

                jobs_to_update = db_enabled_ids & scheduler_job_ids
                for job_id in jobs_to_update:
                    job_info = db_job_map.get(job_id)
                    scheduler_job = scheduler_job_map.get(job_id)
                    job_update_time = db_job_update_time_map.get(job_id)
                    cls._sync_update_job(job_id, job_info, scheduler_job, job_update_time)

        except Exception as e:
            logger.error(f'❌ 任务同步异常: {e}')

    @classmethod
    def _is_job_config_in_sync(cls, scheduler_job: Job, job_info: SchedulerJobInfo) -> bool:
        """
        判断任务配置是否一致

        :param scheduler_job: 调度器任务对象
        :param job_info: 数据库任务对象
        :return: 是否一致
        """
        job_state = scheduler_job.__getstate__()
        job_kwargs = json.loads(job_info.job_kwargs) if job_info.job_kwargs else None
        job_args = job_info.job_args.split(',') if job_info.job_args else None
        job_executor = job_info.job_executor
        if iscoroutinefunction(cls._import_function(job_info.invoke_target)):
            job_executor = 'default'
        expected = {
            'name': job_info.job_name,
            'executor': job_executor,
            'jobstore': job_info.job_group,
            'misfire_grace_time': 1000000000000 if job_info.misfire_policy == '3' else None,
            'coalesce': job_info.misfire_policy == '2',
            'max_instances': 3 if job_info.concurrent == '0' else 1,
            'trigger': str(MyCronTrigger.from_crontab(job_info.cron_expression)),
            'args': tuple(job_args) if job_args else None,
            'kwargs': job_kwargs if job_kwargs else None,
            'func': str(cls._import_function(job_info.invoke_target)),
        }
        current = {
            'name': job_state.get('name'),
            'executor': job_state.get('executor'),
            'jobstore': scheduler_job._jobstore_alias,
            'misfire_grace_time': job_state.get('misfire_grace_time'),
            'coalesce': job_state.get('coalesce'),
            'max_instances': job_state.get('max_instances'),
            'trigger': str(job_state.get('trigger')),
            'args': job_state.get('args'),
            'kwargs': job_state.get('kwargs'),
            'func': str(job_state.get('func')),
        }
        return expected == current

    @classmethod
    def _sync_update_job(
        cls, job_id: str, job_info: SchedulerJobInfo | None, scheduler_job: Job | None, job_update_time: datetime | None
    ) -> None:
        """
        同步更新任务配置

        :param job_id: 任务ID
        :param job_info: 数据库任务对象
        :param scheduler_job: 调度器任务对象
        :param job_update_time: 任务更新时间
        :return: None
        """
        if not job_info or not scheduler_job:
            return
        if cls._should_skip_job_update(job_id, job_update_time):
            return
        if not cls._is_job_config_in_sync(scheduler_job, job_info):
            scheduler.remove_job(job_id=job_id)
            cls._add_job_to_scheduler(job_info)
            logger.info(f'♻️ 同步更新任务: {job_info.job_name}')
        cls._refresh_job_update_cache(job_id, job_update_time)

    @classmethod
    def _should_skip_job_update(cls, job_id: str, job_update_time: datetime | None) -> bool:
        """
        判断是否跳过同步更新

        :param job_id: 任务ID
        :param job_update_time: 任务更新时间
        :return: 是否跳过
        """
        if job_update_time is None:
            return False
        return cls._job_update_time_cache.get(job_id) == job_update_time

    @classmethod
    def _refresh_job_update_cache(cls, job_id: str, job_update_time: datetime | None) -> None:
        """
        刷新任务更新时间缓存

        :param job_id: 任务ID
        :param job_update_time: 任务更新时间
        :return: None
        """
        if job_update_time is not None:
            cls._job_update_time_cache[job_id] = job_update_time
        else:
            cls._job_update_time_cache.pop(job_id, None)

    @classmethod
    async def request_scheduler_sync(cls) -> None:
        """
        请求调度器同步任务状态

        :return: None
        """
        if cls._is_leader:
            cls._sync_pending = True
            cls._ensure_sync_task()
            return
        if cls._redis:
            await cls._redis.publish(cls._sync_channel, cls._worker_id)
        await SchedulerRuntime.publish_sync()

    @classmethod
    def _ensure_sync_task(cls) -> None:
        """
        启动同步调度任务

        :return: None
        """
        if cls._sync_task and not cls._sync_task.done():
            return
        cls._sync_task = asyncio.create_task(cls._run_sync_loop())

    @classmethod
    async def _run_sync_loop(cls) -> None:
        """
        执行同步调度循环

        :return: None
        """
        try:
            while True:
                if not cls._sync_pending:
                    break
                cls._sync_pending = False
                await asyncio.sleep(cls._sync_debounce_seconds)
                await cls._sync_with_throttle()
        except asyncio.CancelledError:
            raise
        finally:
            cls._sync_task = None

    @classmethod
    async def _sync_with_throttle(cls) -> None:
        """
        按节流规则执行同步

        :return: None
        """
        async with cls._sync_lock:
            if not cls._is_leader:
                return
            if cls._last_sync_at:
                elapsed = datetime.now() - cls._last_sync_at
                min_interval = timedelta(seconds=cls._sync_min_interval_seconds)
                if elapsed < min_interval:
                    await asyncio.sleep((min_interval - elapsed).total_seconds())
            await cls._sync_jobs_from_database()
            cls._last_sync_at = datetime.now()

    @classmethod
    def _prepare_scheduler_job_add(cls, job_info: SchedulerJobInfo) -> dict[str, Any]:
        """
        构建调度器任务参数

        :param job_info: 任务对象信息
        :return: 调度器任务参数
        """
        job_func = cls._import_function(job_info.invoke_target)
        job_executor = job_info.job_executor
        if iscoroutinefunction(job_func):
            job_executor = 'default'
        return {
            'func': job_func,
            'trigger': MyCronTrigger.from_crontab(job_info.cron_expression),
            'args': job_info.job_args.split(',') if job_info.job_args else None,
            'kwargs': json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
            'id': str(job_info.job_id),
            'name': job_info.job_name,
            'misfire_grace_time': 1000000000000 if job_info.misfire_policy == '3' else None,
            'coalesce': job_info.misfire_policy == '2',
            'max_instances': 3 if job_info.concurrent == '0' else 1,
            'jobstore': job_info.job_group,
            'executor': job_executor,
        }

    @classmethod
    def _add_job_to_scheduler(cls, job_info: SchedulerJobInfo) -> None:
        """
        内部方法：将任务添加到调度器（不检查应用锁状态，仅供内部使用）

        :param job_info: 任务对象信息
        """
        try:
            # 先移除已存在的同ID任务
            existing_job = scheduler.get_job(job_id=str(job_info.job_id))
            if existing_job:
                scheduler.remove_job(job_id=str(job_info.job_id))
            scheduler.add_job(**cls._prepare_scheduler_job_add(job_info))
        except Exception as e:
            logger.error(f'❌ 添加任务 {job_info.job_name} 失败: {e}')

    @classmethod
    def _import_function(cls, func_path: str) -> Callable[..., Any]:
        """
        动态导入函数

        :param func_path: 函数字符串，如module_task.scheduler_test.job
        :return: 导入的函数对象
        """
        module_path, func_name = func_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, func_name)

    @classmethod
    def get_scheduler_job(cls, job_id: str | int) -> Job:
        """
        根据任务id获取任务对象

        :param job_id: 任务id
        :return: 任务对象
        """
        query_job = scheduler.get_job(job_id=str(job_id))

        return query_job

    @classmethod
    def add_scheduler_job(cls, job_info: SchedulerJobInfo) -> None:
        """
        根据输入的任务对象信息添加任务

        :param job_info: 任务对象信息
        :return:
        """
        # 非应用锁 worker 跳过操作（数据库状态是持久化的，持有应用锁时会加载）
        if not cls._is_leader:
            return
        scheduler.add_job(**cls._prepare_scheduler_job_add(job_info))

    @classmethod
    def execute_scheduler_job_once(cls, job_info: SchedulerJobInfo) -> None:
        """
        根据输入的任务对象执行一次任务

        :param job_info: 任务对象信息
        :return:
        """
        job_func = cls._import_function(job_info.invoke_target)
        job_executor = job_info.job_executor
        if iscoroutinefunction(job_func):
            job_executor = 'default'

        if not cls._is_leader:
            logger.info(f'📍 当前进程不是调度 Leader，忽略本地执行 {job_info.job_name}（应由调度微服务消费命令）')
            return

        # 调度 Leader：通过 scheduler 立即触发一次
        job_trigger = DateTrigger()
        if job_info.status == '0':
            job_trigger = OrTrigger(triggers=[DateTrigger(), MyCronTrigger.from_crontab(job_info.cron_expression)])
        scheduler.add_job(
            func=job_func,
            trigger=job_trigger,
            args=job_info.job_args.split(',') if job_info.job_args else None,
            kwargs=json.loads(job_info.job_kwargs) if job_info.job_kwargs else None,
            id=str(job_info.job_id),
            name=job_info.job_name,
            misfire_grace_time=1000000000000 if job_info.misfire_policy == '3' else None,
            coalesce=job_info.misfire_policy == '2',
            max_instances=3 if job_info.concurrent == '0' else 1,
            jobstore=job_info.job_group,
            executor=job_executor,
        )

    @classmethod
    def remove_scheduler_job(cls, job_id: str | int) -> None:
        """
        根据任务id移除任务

        :param job_id: 任务id
        :return:
        """
        # 非应用锁 worker 跳过操作（数据库状态是持久化的，持有应用锁时会根据状态加载）
        if not cls._is_leader:
            return
        query_job = cls.get_scheduler_job(job_id=job_id)
        if query_job:
            scheduler.remove_job(job_id=str(job_id))

    @classmethod
    async def _execute_async_job_with_log(
        cls, job_func: Callable[..., Any], job_info: SchedulerJobInfo, args: list, kwargs: dict
    ) -> None:
        """
        执行异步任务并记录日志

        :param job_func: 任务函数
        :param job_info: 任务对象信息
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: None
        """
        status = '0'
        exception_info = ''
        job_executor = job_info.job_executor
        if iscoroutinefunction(job_func):
            job_executor = 'default'
        try:
            await job_func(*args, **kwargs)
        except Exception as e:
            status = '1'
            exception_info = str(e)
            logger.error(f'❌ 异步执行任务 {job_info.job_name} 失败: {e}')
        finally:
            cls._record_job_execution_log(job_info, job_executor, status, exception_info)

    @classmethod
    def _record_job_execution_log(cls, job_info: SchedulerJobInfo, job_executor: str, status: str, exception_info: str) -> None:
        """
        记录任务执行日志（用于非 Leader Worker 直接执行任务时）

        :param job_info: 任务对象信息
        :param job_executor: 任务执行器
        :param status: 执行状态 0-成功 1-失败
        :param exception_info: 异常信息
        :return: None
        """
        persistence = get_scheduler_persistence()
        try:
            job_args = job_info.job_args if job_info.job_args else ''
            job_kwargs = job_info.job_kwargs if job_info.job_kwargs else '{}'
            job_trigger = str(MyCronTrigger.from_crontab(job_info.cron_expression)) if job_info.cron_expression else ''
            job_message = (
                f'事件类型: DirectExecution(非Leader), 任务ID: {job_info.job_id}, '
                f'任务名称: {job_info.job_name}, 执行于{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            )
            job_log = persistence.build_execution_log(
                jobName=job_info.job_name,
                jobGroup=job_info.job_group,
                jobExecutor=job_executor,
                invokeTarget=job_info.invoke_target,
                jobArgs=job_args,
                jobKwargs=job_kwargs,
                jobTrigger=job_trigger,
                jobMessage=job_message,
                status=status,
                exceptionInfo=exception_info,
                createTime=datetime.now(),
            )
            session = cls._get_session_local()()
            try:
                persistence.save_execution_log(session, job_log)
            finally:
                session.close()
        except Exception as e:
            logger.error(f'❌ 记录任务执行日志失败: {e}')
