from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import ResponseBaseModel
from module_market.entity.vo.market_vo import (
    IndicatorQueryModel,
    KlineQueryModel,
    MarketAiAnalyzeModel,
    MarketInstrumentQueryModel,
    MarketSyncModel,
)
from module_market.service.market_service import MarketService
from utils.log_util import logger
from utils.response_util import ResponseUtil

market_controller = APIRouterPro(
    prefix='/market', order_num=31, tags=['行情数据'], dependencies=[PreAuthDependency()]
)


@market_controller.get(
    '/instrument/list',
    summary='获取行情标的列表接口',
    description='用于获取行情标的元数据列表（可按category过滤）',
    dependencies=[UserInterfaceAuthDependency('market:instrument:list')],
)
async def get_market_instrument_list(
    request: Request,
    instrument_query: Annotated[MarketInstrumentQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    instrument_list = await MarketService.get_instrument_list_services(query_db, instrument_query)
    logger.info('获取行情标的列表成功')

    return ResponseUtil.success(data=instrument_list)


@market_controller.get(
    '/kline',
    summary='获取K线数据接口',
    description='用于获取指定标的日K线数组',
    dependencies=[UserInterfaceAuthDependency('market:kline:list')],
)
async def get_market_kline(
    request: Request,
    kline_query: Annotated[KlineQueryModel, Query()],
) -> Response:
    klines = await MarketService.get_kline_services(kline_query)
    logger.info(f'获取{kline_query.symbol}的K线成功，共{len(klines)}条')

    return ResponseUtil.success(
        data={'symbol': kline_query.symbol, 'market': kline_query.market, 'klines': klines}
    )


@market_controller.get(
    '/indicators',
    summary='获取技术指标接口',
    description='用于获取指定标的全部技术指标序列（MA/EMA/MACD/RSI/KDJ/BOLL/ATR/CCI/WR/OBV/VOL均线）',
    dependencies=[UserInterfaceAuthDependency('market:indicators:list')],
)
async def get_market_indicators(
    request: Request,
    indicator_query: Annotated[IndicatorQueryModel, Query()],
) -> Response:
    indicators = await MarketService.get_indicators_services(indicator_query)
    logger.info(f'获取{indicator_query.symbol}的技术指标成功')

    return ResponseUtil.success(data=indicators)


@market_controller.post(
    '/sync',
    summary='手动触发行情同步接口',
    description='手动同步行情数据到 Influx（可选symbol，不传则同步全部；无 MySQL 中间层）',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('market:sync')],
)
@Log(title='行情同步', business_type=BusinessType.OTHER)
async def sync_market(
    request: Request,
    sync_body: MarketSyncModel,
) -> Response:
    result = await MarketService.sync_services(sync_body)
    logger.info(f'手动行情同步完成: {result}')

    return ResponseUtil.success(
        data=result,
        msg=f'同步完成，标的{len(result["synced_symbols"])}个，写入Influx {result["total_points"]}点',
    )


@market_controller.post(
    '/sync/mysql-to-influx',
    summary='MySQL历史行情迁移到Influx',
    description='将本库 market_price_history_daily 存量数据迁入时序库（一次性迁移，非日常链路）',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('market:sync')],
)
@Log(title='行情MySQL迁移Influx', business_type=BusinessType.OTHER)
async def migrate_mysql_to_influx(
    request: Request,
    symbol: Annotated[str | None, Query(description='可选，指定标的')] = None,
    market: Annotated[str, Query(description='默认市场')] = 'US',
) -> Response:
    result = await MarketService.migrate_mysql_to_influx_services(symbol=symbol, market=market)
    logger.info(f'MySQL→Influx 迁移完成: {result}')
    return ResponseUtil.success(
        data=result,
        msg=result.get('message') or f'迁移完成，写入 {result.get("total_points", 0)} 点',
    )


@market_controller.post(
    '/ai/analyze',
    summary='AI行情分析接口',
    description='对某标的做AI行情分析（趋势研判/支撑压力/操作建议），结果落库',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
@Log(title='行情AI分析', business_type=BusinessType.OTHER)
async def market_ai_analyze(
    request: Request,
    analyze_body: MarketAiAnalyzeModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await MarketService.ai_analyze_services(query_db, analyze_body)
    logger.info(f'行情AI分析完成: {analyze_body.symbol} -> {result.get("message")}')

    return ResponseUtil.success(data=result, msg=result.get('message', ''))


@market_controller.get(
    '/symbols/{symbol}/overview',
    summary='标的详情概览',
    description='两段式加载：include=core 首屏，include=all 补全历史/简报/内容',
    dependencies=[UserInterfaceAuthDependency('market:symbol:overview')],
)
async def get_symbol_overview(
    request: Request,
    symbol: Annotated[str, Path(description='标的代码')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/CN/HK')] = 'US',
    include: Annotated[str, Query(description='core|all')] = 'core',
    history_limit: Annotated[int, Query(description='历史K线条数')] = 120,
) -> Response:
    data = await MarketService.get_symbol_overview_services(
        query_db, symbol=symbol, market=market, include=include, history_limit=history_limit
    )
    return ResponseUtil.success(data=data)


@market_controller.get(
    '/symbols/{symbol}/history',
    summary='标的历史K线',
    description='查询标的历史日K',
    dependencies=[UserInterfaceAuthDependency('market:kline:list')],
)
async def get_symbol_history(
    request: Request,
    symbol: Annotated[str, Path(description='标的代码')],
    market: Annotated[str, Query()] = 'US',
    limit: Annotated[int, Query()] = 120,
) -> Response:
    klines = await MarketService.get_kline_services(
        KlineQueryModel(symbol=symbol, market=market, start='-2y', stop='now()')
    )
    items = klines[-max(1, min(limit, 500)) :] if klines else []
    return ResponseUtil.success(data={'symbol': symbol, 'market': market, 'items': items, 'count': len(items)})


@market_controller.get(
    '/symbols/{symbol}/content',
    summary='标的公告/资讯/讨论',
    description='读取缓存，可 refresh 强制从长桥刷新',
    dependencies=[UserInterfaceAuthDependency('market:symbol:content')],
)
async def get_symbol_content(
    request: Request,
    symbol: Annotated[str, Path(description='标的代码')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query()] = 'US',
    content_type: Annotated[str, Query(alias='type', description='announcement|news|topic')] = 'news',
    limit: Annotated[int, Query()] = 20,
    refresh: Annotated[bool, Query()] = False,
) -> Response:
    data = await MarketService.get_symbol_content_services(
        query_db, symbol=symbol, market=market, content_type=content_type, limit=limit, refresh=refresh
    )
    return ResponseUtil.success(data=data)


@market_controller.get(
    '/symbols/{symbol}/ai/latest',
    summary='标的最新AI研判',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
async def get_symbol_ai_latest(
    request: Request,
    symbol: Annotated[str, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query()] = 'US',
) -> Response:
    data = await MarketService.get_latest_ai_analysis(query_db, symbol, market)
    return ResponseUtil.success(data=data)


@market_controller.post(
    '/symbols/{symbol}/ai-analyze',
    summary='触发标的AI研判',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
@Log(title='标的AI研判', business_type=BusinessType.OTHER)
async def symbol_ai_analyze(
    request: Request,
    symbol: Annotated[str, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query()] = 'US',
    days: Annotated[int, Query()] = 120,
) -> Response:
    result = await MarketService.ai_analyze_services(
        query_db, MarketAiAnalyzeModel(symbol=symbol, market=market, days=days)
    )
    return ResponseUtil.success(data=result, msg=result.get('message', ''))


@market_controller.get(
    '/finance/briefings',
    summary='财经资讯简报流',
    description='市场筛选 + 内部简报 + 外部新闻聚合',
    dependencies=[UserInterfaceAuthDependency('market:finance:list')],
)
async def get_finance_briefings(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str | None, Query(description='US/CN/HK')] = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 20,
    refresh: Annotated[bool, Query()] = False,
) -> Response:
    data = await MarketService.get_finance_briefings_services(
        query_db, limit=limit, market=market, refresh=refresh
    )
    return ResponseUtil.success(data=data)
