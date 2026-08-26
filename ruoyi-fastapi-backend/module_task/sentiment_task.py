"""
舆情定时任务：供sys_job调度调用
invoke_target: module_task.sentiment_task.collect_and_analyze_job
"""

from utils.job_queue import JobQueue
from utils.log_util import logger


async def collect_and_analyze_job(*args, **kwargs) -> None:
    """
    定时采集舆情并自动AI分析（异步任务）
    """
    if await JobQueue.enqueue('sentiment_collect', {'analyze': True}):
        logger.info('[舆情定时任务] 已入队')
        return
    logger.error('[舆情定时任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def collect_only_job(*args, **kwargs) -> None:
    """
    定时仅采集舆情（异步任务）
    """
    if await JobQueue.enqueue('sentiment_collect', {'analyze': False}):
        logger.info('[舆情采集任务] 已入队')
        return
    logger.error('[舆情采集任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')
