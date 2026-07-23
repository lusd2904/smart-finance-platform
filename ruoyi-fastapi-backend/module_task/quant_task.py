"""
量化策略定时任务：供sys_job调度调用
invoke_target: module_task.quant_task.run_strategy_job
"""

from config.database import AsyncSessionLocal
from module_quant.entity.vo.quant_vo import RunStrategyModel
from module_quant.service.quant_service import QuantService
from utils.log_util import logger


async def run_strategy_job(*args, **kwargs) -> None:
    """
    定时对自选池跑一次策略（异步任务）。

    可选参数：第一个位置参数或 kwargs['profile'] 指定策略档位，默认 balanced。
    建议在每个交易日收盘后调度。
    """
    profile = 'balanced'
    if args and isinstance(args[0], str) and args[0].strip():
        profile = args[0].strip()
    elif kwargs.get('profile'):
        profile = str(kwargs['profile']).strip()

    async with AsyncSessionLocal() as db:
        try:
            result = await QuantService.run_strategy_services(db, RunStrategyModel(profile=profile))
            logger.info(f'[量化定时任务] 执行完成: {result.get("message")}, 信号数={result.get("signalCount")}')
        except Exception as e:
            logger.error(f'[量化定时任务] 执行失败: {e}')
            raise
