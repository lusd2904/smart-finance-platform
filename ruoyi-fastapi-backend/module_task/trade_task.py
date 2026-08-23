"""
自动交易定时扫描：默认仅扫描、不向券商提交委托。
invoke_target: module_task.trade_task.run_auto_trade_scan_job
"""

from config.database import AsyncSessionLocal
from module_trade.service.auto_trade_service import AutoTradeService
from utils.log_util import logger


async def run_auto_trade_scan_job(*args, **kwargs) -> None:
    profile = 'balanced'
    if args and isinstance(args[0], str) and args[0].strip():
        profile = args[0].strip()
    elif kwargs.get('profile'):
        profile = str(kwargs['profile']).strip()

    async with AsyncSessionLocal() as db:
        try:
            result = await AutoTradeService.run_watchlist_strategy_cycle(
                db,
                source='scheduler',
                execute=False,
                strategy_profile=profile,
            )
            logger.info(f'[自动交易定时扫描] {result.get("message")}')
        except Exception as exc:
            logger.error(f'[自动交易定时扫描] 执行失败: {exc}')
            raise


async def run_feishu_push_job(*args, **kwargs) -> None:
    """按用户时区推送飞书策略摘要；非交易日/空清单静默。"""
    from utils.job_queue import JobQueue

    if await JobQueue.enqueue('feishu_push', {}):
        logger.info('[飞书推送] 已入队')
        return
    from module_trade.service.feishu_push_service import FeishuPushService

    async with AsyncSessionLocal() as db:
        result = await FeishuPushService.run_due(db)
        logger.info(f'[飞书推送] {result}')
