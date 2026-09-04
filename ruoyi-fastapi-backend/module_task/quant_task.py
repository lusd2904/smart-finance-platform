"""
量化策略定时任务：供sys_job调度调用
invoke_target: module_task.quant_task.run_strategy_job
invoke_target: module_task.quant_task.run_daily_factor_scan_job
invoke_target: module_task.quant_task.run_position_monitor_job
invoke_target: module_task.quant_task.run_indicator_refresh_job
invoke_target: module_task.quant_task.run_factor_qc_job
"""

from utils.job_queue import JobQueue
from utils.log_util import logger


async def run_strategy_job(*args, **kwargs) -> None:
    """
    定时对自选池跑一次策略（异步任务）。

    可选参数：第一个位置参数或 kwargs['profile'] 覆盖策略档位；不传则各账户用自己绑定的档位。
    kwargs['userId'] 可指定用户（不传则对全部启用自选的用户逐个跑）。
    建议在每个交易日收盘后调度。
    """
    profile = None
    if args and isinstance(args[0], str) and args[0].strip():
        profile = args[0].strip()
    elif kwargs.get('profile'):
        profile = str(kwargs['profile']).strip()
    user_id = int(kwargs.get('userId') or 0) or None
    payload: dict = {}
    if profile:
        payload['profile'] = profile
    if user_id:
        payload['userId'] = user_id

    if await JobQueue.enqueue('strategy_run', payload):
        logger.info(f'[量化定时任务] 已入队 profile={profile} userId={user_id}')
        return
    logger.error('[量化定时任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_daily_factor_scan_job(*args, **kwargs) -> None:
    """全市场收盘后因子全量计算入库。"""
    profile = str(kwargs.get('profile') or (args[0] if args else 'balanced') or 'balanced')
    if await JobQueue.enqueue('factor_scan', {'profile': profile}):
        logger.info(f'[因子日扫任务] 已入队 profile={profile}')
        return
    logger.error('[因子日扫任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_position_monitor_job(*args, **kwargs) -> None:
    """持仓止损 / 止盈 / 移动止损监控。"""
    if await JobQueue.enqueue('position_monitor', {}):
        logger.info('[持仓监控任务] 已入队')
        return
    logger.error('[持仓监控任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_daily_list_scan_job(*args, **kwargs) -> None:
    """A股收盘后扫描次日策略清单。不传 profile 时各账户用绑定档位。"""
    raw = kwargs.get('profile') or (args[0] if args else None)
    payload: dict = {}
    if raw:
        payload['profile'] = str(raw)
    if await JobQueue.enqueue('daily_list_scan', payload):
        logger.info('[次日清单] 扫描已入队')
        return
    logger.error('[次日清单] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_daily_list_open_job(*args, **kwargs) -> None:
    """开盘执行排队的模拟开仓。"""
    if await JobQueue.enqueue('daily_list_open', {}):
        logger.info('[次日清单] 开盘送单已入队')
        return
    logger.error('[次日清单] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_indicator_refresh_job(*args, **kwargs) -> None:
    """行情看板 / 指标快照刷新。"""
    if await JobQueue.enqueue('indicator_refresh', {}):
        logger.info('[指标快照任务] 已入队')
        return
    logger.error('[指标快照任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_factor_qc_job(*args, **kwargs) -> None:
    """Alphalens 风格因子质检（默认美股截面）。"""
    market = str(kwargs.get('market') or (args[0] if args else 'US') or 'US')
    if await JobQueue.enqueue('factor_qc', {'market': market}):
        logger.info(f'[因子质检任务] 已入队 market={market}')
        return
    logger.error('[因子质检任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')
