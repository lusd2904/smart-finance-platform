import asyncio
import json
import os
import socket
from datetime import datetime
from typing import Any

from apscheduler.events import SchedulerEvent
from redis import asyncio as aioredis

from common.constant import SchedulerConstant
from config.env import AppConfig
from config.providers import get_scheduler_persistence
from config.scheduler.jobstores import scheduler
from utils.job_queue import JobQueue
from utils.log_util import logger
from utils.scheduler_runtime import SchedulerRuntime


class EventListenersMixin:
    """
    调度器事件监听、Redis 命令/同步通道监听与心跳上报
    """

    _sync_listener_task: asyncio.Task | None = None
    _command_listener_task: asyncio.Task | None = None

    @classmethod
    async def publish_heartbeat(cls) -> None:
        """
        把调度器存活状态与下次执行时间写入 Redis，供任务页展示。
        """
        jobs = []
        if getattr(scheduler, 'running', False):
            for job in scheduler.get_jobs():
                if str(job.id).startswith('_'):
                    continue
                next_run = getattr(job, 'next_run_time', None)
                jobs.append(
                    {
                        'jobId': str(job.id),
                        'name': job.name,
                        'nextRunTime': next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else None,
                    }
                )
        await SchedulerRuntime.write_heartbeat(
            {
                'alive': True,
                'role': AppConfig.app_role,
                'workerId': cls._worker_id,
                'pid': os.getpid(),
                'hostname': socket.gethostname(),
                'queueDepth': await JobQueue.depth(),
                'running': await JobQueue.running_jobs(),
                'jobs': jobs,
            }
        )

    @classmethod
    async def _handle_runtime_command(cls, raw: Any) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f'⚠️ 忽略无法解析的调度命令: {e}，原始内容: {str(raw)[:200]}')
            return
        if not isinstance(payload, dict):
            return
        action = str(payload.get('action') or '').strip()
        if action == 'sync':
            await cls.request_scheduler_sync()
            return
        if action != 'run' or not cls._is_leader:
            return
        try:
            job_id = int(payload.get('jobId'))
        except (TypeError, ValueError):
            return
        persistence = get_scheduler_persistence()
        async with cls._get_sync_async_session() as session:
            job = await persistence.get_job_detail_by_id(session, job_id)
            if not job:
                logger.warning(f'⚠️ 调度命令 run 找不到任务 {job_id}')
                return
            job_info = persistence.build_job_from_row(job)
        logger.info(f'▶️ 调度微服务收到立即执行命令: {job_info.job_name}')
        cls.execute_scheduler_job_once(job_info)

    @classmethod
    async def _listen_command_channel(cls, redis: aioredis.Redis) -> None:
        """
        监听 API 投递的立即执行 / 同步命令
        """
        while True:
            pubsub = redis.pubsub()
            try:
                await pubsub.subscribe(SchedulerConstant.COMMAND_CHANNEL)
                async for message in pubsub.listen():
                    if not cls._is_leader:
                        continue
                    if message.get('type') != 'message':
                        continue
                    await cls._handle_runtime_command(message.get('data'))
            except asyncio.CancelledError:
                await pubsub.unsubscribe(SchedulerConstant.COMMAND_CHANNEL)
                await pubsub.close()
                raise
            except Exception as e:
                logger.error(f'❌ Scheduler 命令监听异常: {e}，5秒后重试...')
                await pubsub.close()
                await asyncio.sleep(5)
            finally:
                try:
                    await pubsub.close()
                except Exception as e:
                    logger.warning(f'⚠️ 关闭命令通道 PubSub 连接失败: {e}')

    @classmethod
    async def _listen_sync_channel(cls, redis: aioredis.Redis) -> None:
        """
        监听同步请求通道

        :param redis: Redis连接对象
        :return: None
        """
        while True:
            pubsub = redis.pubsub()
            try:
                await pubsub.subscribe(cls._sync_channel)
                async for message in pubsub.listen():
                    if not cls._is_leader:
                        continue
                    if message.get('type') != 'message':
                        continue
                    await cls.request_scheduler_sync()
            except asyncio.CancelledError:
                await pubsub.unsubscribe(cls._sync_channel)
                await pubsub.close()
                raise
            except Exception as e:
                logger.error(f'❌ Scheduler 同步监听异常: {e}，5秒后重试...')
                await pubsub.close()
                await asyncio.sleep(5)
            finally:
                try:
                    await pubsub.close()
                except Exception as e:
                    logger.warning(f'⚠️ 关闭同步通道 PubSub 连接失败: {e}')

    @classmethod
    def scheduler_event_listener(cls, event: SchedulerEvent) -> None:
        """
        调度器事件监听器，记录任务执行日志
        """
        try:
            # 获取事件类型和任务ID
            event_type = event.__class__.__name__
            # 获取任务执行异常信息
            status = '0'
            exception_info = ''
            if event_type == 'JobExecutionEvent' and event.exception:
                exception_info = str(event.exception)
                status = '1'
            if hasattr(event, 'job_id'):
                job_id = event.job_id
                # 跳过内部系统任务（以 _ 开头的任务ID），不记录日志
                if str(job_id).startswith('_'):
                    return
                persistence = get_scheduler_persistence()
                query_job = cls.get_scheduler_job(job_id=job_id)
                if query_job:
                    query_job_info = query_job.__getstate__()
                    # 获取任务名称
                    job_name = query_job_info.get('name')
                    # 获取任务组名
                    job_group = query_job._jobstore_alias
                    # 获取任务执行器
                    job_executor = query_job_info.get('executor')
                    # 获取调用目标字符串
                    invoke_target = query_job_info.get('func')
                    # 获取调用函数位置参数（安全处理）
                    args = query_job_info.get('args')
                    job_args = ','.join(str(arg) for arg in args) if args else ''
                    # 获取调用函数关键字参数
                    kwargs = query_job_info.get('kwargs')
                    job_kwargs = json.dumps(kwargs) if kwargs else '{}'
                    # 获取任务触发器
                    job_trigger = str(query_job_info.get('trigger'))
                    # 构造日志消息
                    job_message = f'事件类型: {event_type}, 任务ID: {job_id}, 任务名称: {job_name}, 执行于{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                    job_log = persistence.build_execution_log(
                        jobName=job_name,
                        jobGroup=job_group,
                        jobExecutor=job_executor,
                        invokeTarget=invoke_target,
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
            logger.error(f'❌ 调度任务事件监听器异常: {e}')
