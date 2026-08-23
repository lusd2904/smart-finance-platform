"""
行情定时任务：供sys_job调度调用
invoke_target: module_task.market_task.sync_market_job

每日收盘后增量同步目标标的行情数据到InfluxDB。
同步本身为同步IO（pymysql/httpx/influx），放入线程池执行避免阻塞事件循环。
"""

import asyncio
from typing import Any

from config.database import AsyncSessionLocal
from module_market.entity.vo.market_vo import MarketSyncModel
from module_market.service.market_service import MarketService
from module_market.service.sync_service import MarketSyncService
from utils.job_queue import JobQueue
from utils.log_util import logger


async def sync_market_job(*args, **kwargs) -> None:
    """
    定时增量同步行情（异步任务）。
    先确保标的元数据已初始化，再增量同步全部目标标的近10年数据。
    """
    async with AsyncSessionLocal() as db:
        try:
            await MarketService.init_instruments_services(db)
        except Exception as e:
            logger.warning(f'[行情定时任务] 初始化标的元数据失败(忽略继续): {e}')

    if await JobQueue.enqueue('market_sync', {'years': 10}):
        logger.info('[行情定时任务] 已入队 Redis 后台队列')
        return
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, MarketSyncService.sync, None, 10)
        logger.info(f'[行情定时任务] 执行完成: 标的{len(result["synced_symbols"])}个，写入{result["total_points"]}点')
    except Exception as e:
        logger.error(f'[行情定时任务] 执行失败: {e}')
        raise


async def sync_klines_slow_job(*args, **kwargs) -> None:
    """
    慢速同步全市场日K（源级限流、精选优先、已有新K线则跳过）。
    invoke_target: module_task.market_task.sync_klines_slow_job
    """
    from module_market.service.sync_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        MarketSyncService,
    )

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: MarketSyncService.sync_universe(years=10, include_listed=True),
        )
        logger.info(
            f'[慢速K线] 完成 scanned={result.get("scanned")} '
            f'synced={len(result.get("synced_symbols") or [])} '
            f'skip={len(result.get("skipped") or [])} fail={len(result.get("failed") or [])}'
        )
    except Exception as e:
        logger.error(f'[慢速K线] 失败: {e}')
        raise


async def sync_listings_job(*args, **kwargs) -> None:
    """
    同步美股/A股/港股全市场代码到 market_instrument。
    invoke_target: module_task.market_task.sync_listings_job
    """
    from module_market.service.listing_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        ListingService,
    )

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, ListingService.sync)
        logger.info(f'[全市场代码] 同步完成: {result}')
    except Exception as e:
        logger.error(f'[全市场代码] 同步失败: {e}')
        raise


async def sync_symbol_job(symbol: str, *args, **kwargs) -> None:
    """
    定时同步单个标的（异步任务）。
    """
    try:
        result = await MarketService.sync_services(MarketSyncModel(symbol=symbol, years=10))
        logger.info(f'[行情同步任务] {symbol} 执行完成: {result}')
    except Exception as e:
        logger.error(f'[行情同步任务] {symbol} 执行失败: {e}')
        raise


async def refresh_finance_briefings_job(*args, **kwargs) -> None:
    """
    定时刷新财经资讯简报流。
    invoke_target: module_task.market_task.refresh_finance_briefings_job
    """
    from module_market.service.finance_news_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        FinanceNewsService,
    )

    if await JobQueue.enqueue('finance_briefings', {}):
        logger.info('[财经资讯定时任务] 已入队')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await FinanceNewsService.refresh_all_markets(db)
            logger.info(f'[财经资讯定时任务] 完成: {result}')
        except Exception as e:
            logger.error(f'[财经资讯定时任务] 失败: {e}')
            raise


async def refresh_symbol_content_now() -> dict[str, Any]:
    from module_market.service.content_cache_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        SymbolContentService,
    )
    from utils.longbridge_breaker import LongbridgeBreaker  # noqa: PLC0415 - 定时任务入口延迟加载服务，缩短模块导入链

    if not LongbridgeBreaker.allow():
        return {'skipped': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'total': 0}

    hot = ['AAPL', 'NVDA', 'MSFT', 'TSLA', '0700.HK', '9988.HK']
    markets = {
        'AAPL': 'US',
        'NVDA': 'US',
        'MSFT': 'US',
        'TSLA': 'US',
        '0700.HK': 'HK',
        '9988.HK': 'HK',
    }
    async with AsyncSessionLocal() as db:
        total = 0
        for sym in hot:
            try:
                clean = sym.replace('.HK', '').replace('.US', '').replace('.SH', '').replace('.SZ', '')
                mkt = markets.get(sym, 'US')
                total += await SymbolContentService.refresh_symbol(db, clean if mkt == 'US' else sym.split('.')[0], mkt)
            except Exception as e:  # noqa: PERF203 - 单标的失败不中断整批
                logger.warning(f'[内容缓存任务] {sym} 失败: {e}')
        logger.info(f'[内容缓存任务] 完成，合计写入约{total}条')
        return {'total': total}


async def refresh_symbol_content_job(*args, **kwargs) -> None:
    """
    定时刷新热门标的公告/资讯/讨论缓存。
    invoke_target: module_task.market_task.refresh_symbol_content_job
    """
    if await JobQueue.enqueue('symbol_content', {}):
        logger.info('[内容缓存任务] 已入队')
        return
    await refresh_symbol_content_now()


async def analyze_watchlist_job(*args, **kwargs) -> None:
    """
    每小时对行情自选清单做综合分析（指标 + 长桥资讯 + 舆情）。
    invoke_target: module_task.market_task.analyze_watchlist_job
    """
    from module_market.service.watchlist_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        MarketWatchlistService,
    )

    if await JobQueue.enqueue('watchlist_analyze', {}):
        logger.info('[自选综合分析任务] 已入队 Redis 后台队列')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await MarketWatchlistService.run_hourly_job(db)
            logger.info(
                f'[自选综合分析任务] 完成: count={result.get("count")} failed={result.get("failedCount")} '
                f'ai={result.get("aiAvailable")}'
            )
        except Exception as e:
            logger.error(f'[自选综合分析任务] 失败: {e}')
            raise


async def _collect_market_heat(market: str, trade_date: str | None = None) -> None:
    from module_market.service.heat_service import (  # noqa: PLC0415 - 定时任务入口延迟加载，缩短模块导入链
        MarketHeatService,
    )

    payload = {'market': market.upper(), 'tradeDate': trade_date}
    if await JobQueue.enqueue('market_heat_collect', payload):
        logger.info(f'[热度采集任务] 已入队 market={market}')
        return
    async with AsyncSessionLocal() as db:
        try:
            result = await MarketHeatService.collect_market(db, market=market, trade_date=trade_date)
            logger.info(f'[热度采集任务] 完成 market={market}: {result}')
        except Exception as e:
            logger.error(f'[热度采集任务] 失败 market={market}: {e}')
            raise


async def collect_market_heat_us_job(*args, **kwargs) -> None:
    """美股收盘后采集热度与 Top50。invoke_target: module_task.market_task.collect_market_heat_us_job"""
    await _collect_market_heat('US')


async def collect_market_heat_hk_job(*args, **kwargs) -> None:
    """港股收盘后采集热度与 Top50。invoke_target: module_task.market_task.collect_market_heat_hk_job"""
    await _collect_market_heat('HK')


async def collect_market_heat_cn_job(*args, **kwargs) -> None:
    """A股收盘后采集热度与 Top50。invoke_target: module_task.market_task.collect_market_heat_cn_job"""
    await _collect_market_heat('CN')


async def _eod_kline_sync(market: str) -> dict[str, Any]:
    from module_market.service.sync_service import MarketSyncService  # noqa: PLC0415

    payload = {'market': market.upper()}
    if await JobQueue.enqueue('eod_kline_sync', payload):
        logger.info(f'[收盘K线] 已入队 market={market}')
        return {'queued': True, 'market': market}
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: MarketSyncService.sync_eod_market(market))
    logger.info(f'[收盘K线] 完成 market={market}: {result}')
    return result


async def eod_kline_sync_cn_job(*args, **kwargs) -> None:
    """A股收盘后拉日K+分时。invoke_target: module_task.market_task.eod_kline_sync_cn_job"""
    await _eod_kline_sync('CN')


async def eod_kline_sync_hk_job(*args, **kwargs) -> None:
    """港股收盘后拉日K+分时。invoke_target: module_task.market_task.eod_kline_sync_hk_job"""
    await _eod_kline_sync('HK')


async def eod_kline_sync_us_job(*args, **kwargs) -> None:
    """美股收盘后拉日K+分时。invoke_target: module_task.market_task.eod_kline_sync_us_job"""
    await _eod_kline_sync('US')


async def run_stock_pick_job(*args, **kwargs) -> None:
    """智能选股扫描。invoke_target: module_task.market_task.run_stock_pick_job"""
    from module_market.service.stock_pick_service import StockPickService  # noqa: PLC0415

    payload = {'trigger': 'schedule'}
    if await JobQueue.enqueue('stock_pick_run', payload):
        logger.info('[选股] 已入队')
        return
    async with AsyncSessionLocal() as db:
        result = await StockPickService.run(db, trigger='schedule', use_ai=True)
        logger.info(
            f'[选股] 完成 status={result.get("status")} picked={result.get("pickedCount")} ai={result.get("aiCount")}'
        )

