"""
舆情定时任务：供sys_job调度调用
invoke_target: module_task.sentiment_task.collect_and_analyze_job
"""

from config.database import AsyncSessionLocal
from module_sentiment.service.sentiment_service import SentimentService
from utils.log_util import logger


async def collect_and_analyze_job(*args, **kwargs) -> None:
    """
    定时采集舆情并自动AI分析（异步任务）
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await SentimentService.collect_and_analyze_services(db)
            logger.info(f'[舆情定时任务] 执行完成: {result}')
        except Exception as e:
            logger.error(f'[舆情定时任务] 执行失败: {e}')
            raise


async def collect_only_job(*args, **kwargs) -> None:
    """
    定时仅采集舆情（异步任务）
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await SentimentService.collect_news_services(db)
            logger.info(f'[舆情采集任务] 执行完成: {result}')
        except Exception as e:
            logger.error(f'[舆情采集任务] 执行失败: {e}')
            raise
