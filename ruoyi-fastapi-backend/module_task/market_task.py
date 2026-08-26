"""
行情定时任务：供sys_job调度调用
invoke_target: module_task.market_task.sync_market_job

每日收盘后增量同步目标标的行情数据到InfluxDB。
同步本身为同步IO（pymysql/httpx/influx），放入线程池执行避免阻塞事件循环。
"""

from typing import Any

from config.database import AsyncSessionLocal
from module_market.entity.vo.market_vo import MarketSyncModel
from module_market.service.market_service import MarketService
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
    logger.error('[行情定时任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def sync_klines_slow_job(*args, **kwargs) -> None:
    """
    慢速同步全市场日K（源级限流、精选优先、已有新K线则跳过）。
    invoke_target: module_task.market_task.sync_klines_slow_job
    """
    years = int(kwargs.get('years') or 10)
    if await JobQueue.enqueue('klines_slow', {'years': years}):
        logger.info(f'[慢速K线] 已入队 years={years}')
        return
    logger.error('[慢速K线] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def sync_listings_job(*args, **kwargs) -> None:
    """
    同步美股/A股/港股全市场代码到 market_instrument。
    invoke_target: module_task.market_task.sync_listings_job
    """
    if await JobQueue.enqueue('listings_sync', {}):
        logger.info('[全市场代码] 已入队')
        return
    logger.error('[全市场代码] 入队失败，跳过本轮（不在 scheduler 内联执行）')


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
    if await JobQueue.enqueue('finance_briefings', {}):
        logger.info('[财经资讯定时任务] 已入队')
        return
    logger.error('[财经资讯定时任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def refresh_symbol_content_now() -> dict[str, Any]:
    from module_market.service.content_cache_service import (
        SymbolContentService,
    )
    from utils.longbridge_breaker import LongbridgeBreaker

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
    logger.error('[内容缓存任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def analyze_market_review_job(*args, **kwargs) -> None:
    """
    收盘后三市场复盘。kwargs['markets'] 或第一个位置参数为 US/HK/CN，逗号分隔；默认三个市场。
    invoke_target: module_task.market_task.analyze_market_review_job
    """
    raw = kwargs.get('markets') or kwargs.get('market')
    if isinstance(raw, (list, tuple)):
        markets = [str(p).strip().upper() for p in raw if str(p).strip()]
    elif args:
        markets = [str(p).strip().upper() for p in args if str(p).strip()]
    else:
        markets = [p.strip().upper() for p in str(raw or '').split(',') if p.strip()]
    markets = markets or None
    if await JobQueue.enqueue('market_review', {'markets': markets}):
        logger.info(f'[市场复盘任务] 已入队 markets={markets or "ALL"}')
        return
    logger.error('[市场复盘任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def analyze_watchlist_job(*args, **kwargs) -> None:
    """
    每小时对行情自选清单做综合分析（指标 + 长桥资讯 + 舆情）。
    invoke_target: module_task.market_task.analyze_watchlist_job
    """
    if await JobQueue.enqueue('watchlist_analyze', {}):
        logger.info('[自选综合分析任务] 已入队 Redis 后台队列')
        return
    logger.error('[自选综合分析任务] 入队失败，跳过本轮（不在 scheduler 内联执行）')


async def _collect_market_heat(market: str, trade_date: str | None = None) -> None:
    payload = {'market': market.upper(), 'tradeDate': trade_date}
    if await JobQueue.enqueue('market_heat_collect', payload):
        logger.info(f'[热度采集任务] 已入队 market={market}')
        return
    logger.error(f'[热度采集任务] 入队失败，跳过本轮（不在 scheduler 内联执行） market={market}')


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
    payload = {'market': market.upper()}
    if await JobQueue.enqueue('eod_kline_sync', payload):
        logger.info(f'[收盘K线] 已入队 market={market}')
        return {'queued': True, 'market': market}
    logger.error(f'[收盘K线] 入队失败，跳过本轮（不在 scheduler 内联执行） market={market}')
    return {'queued': False, 'skipped': True, 'market': market}


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
    payload = {'trigger': 'schedule'}
    if await JobQueue.enqueue('stock_pick_run', payload):
        logger.info('[选股] 已入队')
        return
    logger.error('[选股] 入队失败，跳过本轮（不在 scheduler 内联执行）')
