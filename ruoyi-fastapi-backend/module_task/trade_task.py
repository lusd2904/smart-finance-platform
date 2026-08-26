"""
自动交易定时扫描：按用户逐个隔离执行，默认仅扫描、不向券商提交委托。
invoke_target: module_task.trade_task.run_auto_trade_scan_job
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from config.database import AsyncSessionLocal
from module_quant.dao.quant_dao import QuantWatchlistDao
from module_trade.service.auto_trade_service import AutoTradeService
from utils.job_queue import JobQueue
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _parse_scan_args(*args, **kwargs) -> tuple[str, int | None]:
    profile = 'balanced'
    if args and isinstance(args[0], str) and args[0].strip():
        profile = args[0].strip()
    elif kwargs.get('profile'):
        profile = str(kwargs['profile']).strip()
    user_id = int(kwargs.get('userId') or 0) or None
    return profile, user_id


async def _scan_one_user(db: AsyncSession, uid: int, profile: str) -> None:
    """单用户自动交易扫描。该账户开关打开则真实下单，否则只评估。"""
    try:
        settings = await AutoTradeService.load_user_trade_settings(db, uid)
        result = await AutoTradeService.run_watchlist_strategy_cycle(
            db,
            source='scheduler',
            execute=bool(settings.get('auto_trade_enabled')),
            strategy_profile=profile,
            user_id=uid,
        )
        logger.info(
            f'[自动交易定时扫描] user={uid} auto={settings.get("auto_trade_enabled")} {result.get("message")}'
        )
    except Exception as exc:
        logger.error(f'[自动交易定时扫描] user={uid} 执行失败: {exc}')


async def run_auto_trade_scan_now(profile: str = 'balanced', user_id: int | None = None) -> dict[str, Any]:
    """队列消费者执行的自动交易扫描。是否真实下单仍跟各账户 auto_trade_enabled。"""
    async with AsyncSessionLocal() as db:
        try:
            if user_id:
                await _scan_one_user(db, user_id, profile)
            else:
                from module_quant.dao.quant_dao import QuantLongbridgeConfigDao

                watch_users = await QuantWatchlistDao.distinct_users(db)
                key_users = await QuantLongbridgeConfigDao.list_configured_user_ids(db)
                users = sorted({int(u) for u in [*watch_users, *key_users] if u}) or [1]
                for uid in users:
                    await _scan_one_user(db, uid, profile)
        except Exception as exc:
            logger.error(f'[自动交易定时扫描] 执行失败: {exc}')
            raise
    return {'profile': profile, 'userId': user_id}


async def run_auto_trade_scan_job(*args, **kwargs) -> None:
    profile, user_id = _parse_scan_args(*args, **kwargs)
    payload: dict[str, Any] = {'profile': profile}
    if user_id:
        payload['userId'] = user_id
    if await JobQueue.enqueue('auto_trade_scan', payload):
        logger.info('[自动交易定时扫描] 已入队')
        return
    logger.error('[自动交易定时扫描] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def run_feishu_push_job(*args, **kwargs) -> None:
    """按用户时区推送飞书策略摘要；非交易日/空清单静默。"""
    if await JobQueue.enqueue('feishu_push', {}):
        logger.info('[飞书推送] 已入队')
        return
    logger.error('[飞书推送] 入队失败，跳过本轮（不在 scheduler 内联执行）')
