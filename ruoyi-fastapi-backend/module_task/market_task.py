"""
行情定时任务：供sys_job调度调用
invoke_target: module_task.market_task.sync_market_job

每日收盘后增量同步目标标的行情数据到InfluxDB。
同步本身为同步IO（pymysql/httpx/influx），放入线程池执行避免阻塞事件循环。
"""

import asyncio

from config.database import AsyncSessionLocal
from module_market.entity.vo.market_vo import MarketSyncModel
from module_market.service.market_service import MarketService
from module_market.service.sync_service import MarketSyncService
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

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, MarketSyncService.sync, None, 10)
        logger.info(f'[行情定时任务] 执行完成: 标的{len(result["synced_symbols"])}个，写入{result["total_points"]}点')
    except Exception as e:
        logger.error(f'[行情定时任务] 执行失败: {e}')
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
    from module_market.service.finance_news_service import FinanceNewsService

    async with AsyncSessionLocal() as db:
        try:
            result = await FinanceNewsService.refresh_all_markets(db)
            logger.info(f'[财经资讯定时任务] 完成: {result}')
        except Exception as e:
            logger.error(f'[财经资讯定时任务] 失败: {e}')
            raise


async def refresh_symbol_content_job(*args, **kwargs) -> None:
    """
    定时刷新热门标的公告/资讯/讨论缓存。
    invoke_target: module_task.market_task.refresh_symbol_content_job
    """
    from module_market.service.content_cache_service import SymbolContentService

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
                # 内部统一用无后缀代码
                clean = sym.replace('.HK', '').replace('.US', '').replace('.SH', '').replace('.SZ', '')
                mkt = markets.get(sym, 'US')
                total += await SymbolContentService.refresh_symbol(db, clean if mkt == 'US' else sym.split('.')[0], mkt)
            except Exception as e:
                logger.warning(f'[内容缓存任务] {sym} 失败: {e}')
        logger.info(f'[内容缓存任务] 完成，合计写入约{total}条')


async def analyze_watchlist_job(*args, **kwargs) -> None:
    """
    每小时对行情自选清单做综合分析（指标 + 长桥资讯 + 舆情）。
    invoke_target: module_task.market_task.analyze_watchlist_job
    """
    from module_market.service.watchlist_service import MarketWatchlistService

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

