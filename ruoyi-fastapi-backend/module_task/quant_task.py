"""
量化策略定时任务：供sys_job调度调用
invoke_target: module_task.quant_task.run_strategy_job
invoke_target: module_task.quant_task.run_daily_factor_scan_job
invoke_target: module_task.quant_task.run_position_monitor_job
invoke_target: module_task.quant_task.run_indicator_refresh_job
invoke_target: module_task.quant_task.run_factor_qc_job
"""

from config.database import AsyncSessionLocal
from module_quant.dao.quant_dao import QuantWatchlistDao
from module_quant.entity.vo.quant_vo import RunStrategyModel
from module_quant.service.quant_service import QuantService
from module_quant.service.snapshot_service import SnapshotService
from utils.job_queue import JobQueue
from utils.log_util import logger


async def run_strategy_job(*args, **kwargs) -> None:
    """
    定时对自选池跑一次策略（异步任务）。

    可选参数：第一个位置参数或 kwargs['profile'] 指定策略档位，默认 balanced。
    kwargs['userId'] 可指定用户（不传则对全部启用自选的用户逐个跑）。
    建议在每个交易日收盘后调度。
    """
    profile = 'balanced'
    if args and isinstance(args[0], str) and args[0].strip():
        profile = args[0].strip()
    elif kwargs.get('profile'):
        profile = str(kwargs['profile']).strip()
    user_id = int(kwargs.get('userId') or 0) or None

    if await JobQueue.enqueue('strategy_run', {'profile': profile, 'userId': user_id}):
        logger.info(f'[量化定时任务] 已入队 profile={profile} userId={user_id}')
        return
    async with AsyncSessionLocal() as db:
        try:
            if user_id:
                result = await QuantService.run_strategy_services(
                    db, RunStrategyModel(profile=profile), user_id=user_id
                )
                logger.info(f'[量化定时任务] 执行完成: {result.get("message")}, 信号数={result.get("signalCount")}')
            else:
                # 未指定用户：对每个有启用自选的账号各跑一次
                users = (await QuantWatchlistDao.distinct_users(db)) or [1]
                for uid in users:
                    result = await QuantService.run_strategy_services(
                        db, RunStrategyModel(profile=profile), user_id=uid
                    )
                    logger.info(
                        f'[量化定时任务] user={uid} 完成: 信号数={result.get("signalCount")}'
                    )
        except Exception as e:
            logger.error(f'[量化定时任务] 执行失败: {e}')
            raise


async def run_daily_factor_scan_job(*args, **kwargs) -> None:
    """全市场收盘后因子全量计算入库。"""
    profile = str(kwargs.get('profile') or (args[0] if args else 'balanced') or 'balanced')
    if await JobQueue.enqueue('factor_scan', {'profile': profile}):
        logger.info(f'[因子日扫任务] 已入队 profile={profile}')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await SnapshotService.run_daily_factor_scan(db, profile=profile)
            logger.info(
                f'[因子日扫任务] 完成: 成功={result.get("symbolCount")} 失败={result.get("failedCount")}'
            )
        except Exception as e:
            logger.error(f'[因子日扫任务] 失败: {e}')
            raise


async def run_position_monitor_job(*args, **kwargs) -> None:
    """持仓异动与止损监控。"""
    from utils.longbridge_breaker import LongbridgeBreaker  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链

    if await JobQueue.enqueue('position_monitor', {}):
        logger.info('[持仓监控任务] 已入队')
        return
    if not LongbridgeBreaker.allow():
        logger.info(f'[持仓监控任务] 跳过: {LongbridgeBreaker.blocked_message()}')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await SnapshotService.run_position_monitor(db)
            logger.info(
                f'[持仓监控任务] 完成: configured={result.get("configured")} alerts={result.get("alertCount")}'
            )
        except Exception as e:
            logger.error(f'[持仓监控任务] 失败: {e}')
            raise


async def run_daily_list_scan_job(*args, **kwargs) -> None:
    """A股收盘后扫描次日策略清单。"""
    profile = str(kwargs.get('profile') or (args[0] if args else 'balanced') or 'balanced')
    if await JobQueue.enqueue('daily_list_scan', {'profile': profile}):
        logger.info('[次日清单] 扫描已入队')
        return
    from module_quant.service.daily_list_service import (  # noqa: PLC0415 - 定时任务入口延迟加载服务，缩短模块导入链
        DailyListService,
    )

    async with AsyncSessionLocal() as db:
        result = await DailyListService.scan_all_users(db, profile)
        logger.info(f'[次日清单] 扫描完成: {result}')


async def run_daily_list_open_job(*args, **kwargs) -> None:
    """开盘执行排队的模拟开仓。"""
    if await JobQueue.enqueue('daily_list_open', {}):
        logger.info('[次日清单] 开盘送单已入队')
        return
    from module_quant.service.daily_list_service import (  # noqa: PLC0415 - 定时任务入口延迟加载服务，缩短模块导入链
        DailyListService,
    )

    async with AsyncSessionLocal() as db:
        result = await DailyListService.execute_queued(db)
        logger.info(f'[次日清单] 开盘送单完成: {result}')


async def run_indicator_refresh_job(*args, **kwargs) -> None:
    """行情看板 / 指标快照刷新。"""
    if await JobQueue.enqueue('indicator_refresh', {}):
        logger.info('[指标快照任务] 已入队')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await SnapshotService.run_indicator_refresh(db)
            logger.info(f'[指标快照任务] 完成: count={result.get("count")}')
        except Exception as e:
            logger.error(f'[指标快照任务] 失败: {e}')
            raise


async def run_factor_qc_job(*args, **kwargs) -> None:
    """Alphalens 风格因子质检（默认美股截面）。"""
    from module_quant.service.factor_qc_service import (  # noqa: PLC0415 - 定时任务入口延迟加载服务，缩短模块导入链
        FactorQcService,
    )

    market = str(kwargs.get('market') or (args[0] if args else 'US') or 'US')
    if await JobQueue.enqueue('factor_qc', {'market': market}):
        logger.info(f'[因子质检任务] 已入队 market={market}')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await FactorQcService.run_and_store(db, market=market)
            logger.info(
                f'[因子质检任务] 完成: market={market} items={result.get("itemCount")} saved={result.get("saved")}'
            )
        except Exception as e:
            logger.error(f'[因子质检任务] 失败: {e}')
            raise
