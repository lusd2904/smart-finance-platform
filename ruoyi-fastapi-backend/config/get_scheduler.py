"""
定时任务调度门面模块。

实现已按职责拆分至 config/scheduler 子包：
- jobstores.py: 调度器实例、jobstore/引擎懒加载资源管理
- triggers.py: MyCronTrigger 自定义 Cron 触发器
- leader_election.py: 基于 Redis 锁的 Leader 选举与锁生命周期
- job_crud.py: 任务增删改查、数据库状态同步与执行日志
- event_listeners.py: 事件监听、命令/同步通道监听与心跳上报

本模块保留原有公开符号（SchedulerUtil、scheduler、MyCronTrigger 等），
外部导入路径零变化。
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.scheduler.event_listeners import EventListenersMixin
from config.scheduler.job_crud import JobCrudMixin
from config.scheduler.jobstores import (
    SchedulerEngineMixin,
    job_defaults,
    redis_config,
    scheduler,
)
from config.scheduler.leader_election import LeaderElectionMixin
from config.scheduler.triggers import MyCronTrigger


class SchedulerUtil(LeaderElectionMixin, JobCrudMixin, EventListenersMixin, SchedulerEngineMixin):
    """
    定时任务相关方法
    """


__all__ = ['AsyncIOScheduler', 'MyCronTrigger', 'SchedulerUtil', 'job_defaults', 'redis_config', 'scheduler']
