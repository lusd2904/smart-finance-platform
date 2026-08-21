from typing import Annotated

from fastapi import Body, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from exceptions.exception import ServiceException
from module_admin.entity.vo.user_vo import CurrentUserModel
from common.enums import BusinessType
from common.router import APIRouterPro
from common.vo import PageResponseModel, ResponseBaseModel
from module_market.entity.vo.market_vo import (
    AddMarketWatchlistModel,
    IndicatorQueryModel,
    KlineQueryModel,
    MarketAiAnalyzeModel,
    MarketInstrumentQueryModel,
    MarketSyncModel,
    MarketWatchlistAnalyzeModel,
    MarketWatchlistModel,
    MarketWatchlistPageQueryModel,
)
from module_market.service.market_service import MarketService
from module_market.service.heat_service import MarketHeatService
from module_market.service.watchlist_service import MarketWatchlistService
from utils.job_queue import JobQueue
from utils.log_util import logger
from utils.response_util import ResponseUtil


def _current_user_id(current_user: CurrentUserModel) -> int:
    user = current_user.user if current_user else None
    user_id = getattr(user, 'user_id', None) if user else None
    if not user_id:
        raise ServiceException(message='无法识别当前用户')
    return int(user_id)

market_controller = APIRouterPro(
    prefix='/market', order_num=31, tags=['行情数据'], dependencies=[PreAuthDependency()]
)


import json  # noqa: E402
import time  # noqa: E402
from module_market.service.tradingview_service import TradingViewDatafeedService  # noqa: E402


@market_controller.get('/tradingview/config', summary='TradingView 配置')
async def tradingview_config(request: Request) -> Response:
    return Response(content=json.dumps(TradingViewDatafeedService.get_config()), media_type='application/json')


@market_controller.get('/tradingview/symbols', summary='TradingView 标的信息')
async def tradingview_symbols(
    request: Request, symbol: Annotated[str, Query(description='标的代码')] = 'AAPL.US'
) -> Response:
    return Response(
        content=json.dumps(TradingViewDatafeedService.get_symbol_info(symbol)), media_type='application/json'
    )


@market_controller.get('/tradingview/history', summary='TradingView K线历史')
async def tradingview_history(
    request: Request,
    symbol: Annotated[str, Query(description='标的代码')],
    from_ts: Annotated[int | None, Query(alias='from')] = None,
    to_ts: Annotated[int | None, Query(alias='to')] = None,
    resolution: Annotated[str, Query()] = 'D',
) -> Response:
    bars = await TradingViewDatafeedService.get_history_bars(
        symbol=symbol, from_ts=from_ts, to_ts=to_ts, resolution=resolution
    )
    return Response(content=json.dumps(bars), media_type='application/json')


@market_controller.get('/tradingview/time', summary='TradingView 服务端时间')
async def tradingview_time(request: Request) -> Response:
    return Response(content=str(int(time.time())), media_type='text/plain')


@market_controller.get(
    '/board/quotes',
    summary='行情台批量报价',
    description='一次返回全部标的最近两根日K（Influx）。长桥密钥为空时仅用时序库，不编造价格。',
    dependencies=[UserInterfaceAuthDependency('market:kline:list')],
)
async def get_market_board_quotes(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    category: Annotated[str | None, Query(description='可选分类')] = None,
    market: Annotated[str | None, Query(description='可选市场')] = None,
) -> Response:
    data = await MarketService.get_board_quotes_services(query_db, category=category, market=market)
    return ResponseUtil.success(data=data)


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
    ticket = await JobQueue.submit(
        'market_sync',
        {'years': getattr(sync_body, 'years', None) or 10, 'symbol': getattr(sync_body, 'symbol', None)},
    )
    if not ticket:
        raise ServiceException(message='后台任务队列暂不可用，请稍后重试')
    logger.info(f'手动行情同步已入队: {ticket}')
    return ResponseUtil.success(data=ticket, msg='已加入后台队列，稍后刷新查看结果')


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
    '/ai/analyze/stream',
    summary='AI行情分析流式接口(SSE)',
    description='对某标的做AI行情流式打字机分析输出',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
async def market_ai_analyze_stream(
    request: Request,
    symbol: Annotated[str, Query(description='标的代码')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/CN/HK')] = 'US',
    days: Annotated[int, Query(description='分析天数')] = 90,
) -> StreamingResponse:
    analyze_body = MarketAiAnalyzeModel(symbol=symbol, market=market, days=days)
    stream_gen = MarketService.ai_analyze_stream_services(query_db, analyze_body)
    return StreamingResponse(stream_gen, media_type='text/event-stream')


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
    try:
        data = await MarketService.get_finance_briefings_services(
            query_db, limit=limit, market=market, refresh=refresh
        )
    except Exception as exc:
        logger.warning(f'[财经资讯] 接口降级空列表: {exc}')
        data = {
            'success': True,
            'data': [],
            'message': '财经资讯源暂时不可用，已返回空列表，请稍后重试',
            'meta': {'count': 0, 'market': market},
        }
    msg = data.get('message') or '操作成功'
    return ResponseUtil.success(data=data, msg=msg)


@market_controller.get(
    '/watchlist/overview',
    summary='行情自选清单总览',
    description='启用自选 + 最新报价 + 最近一次综合分析',
    dependencies=[UserInterfaceAuthDependency('market:watchlist:list')],
)
async def get_market_watchlist_overview(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MarketWatchlistService.overview_services(query_db, _current_user_id(current_user))
    return ResponseUtil.success(data=data)


@market_controller.get(
    '/watchlist/list',
    summary='行情自选清单分页',
    response_model=PageResponseModel[MarketWatchlistModel],
    dependencies=[UserInterfaceAuthDependency('market:watchlist:list')],
)
async def get_market_watchlist_list(
    request: Request,
    watchlist_page_query: Annotated[MarketWatchlistPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    result = await MarketWatchlistService.get_list_services(
        query_db, watchlist_page_query, is_page=True, user_id=_current_user_id(current_user)
    )
    return ResponseUtil.success(model_content=result)


@market_controller.post(
    '/watchlist',
    summary='新增行情自选',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('market:watchlist:add')],
)
@Log(title='行情自选清单', business_type=BusinessType.INSERT)
async def add_market_watchlist(
    request: Request,
    add_model: AddMarketWatchlistModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    result = await MarketWatchlistService.add_services(query_db, add_model, _current_user_id(current_user))
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


@market_controller.delete(
    '/watchlist/{ids}',
    summary='删除行情自选',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('market:watchlist:remove')],
)
@Log(title='行情自选清单', business_type=BusinessType.DELETE)
async def delete_market_watchlist(
    request: Request,
    ids: Annotated[str, Path(description='需要删除的自选ID')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    result = await MarketWatchlistService.delete_services(query_db, ids, _current_user_id(current_user))
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


@market_controller.get(
    '/watchlist/analysis',
    summary='自选综合分析历史',
    dependencies=[UserInterfaceAuthDependency('market:watchlist:list')],
)
async def get_market_watchlist_analysis(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query()] = 'US',
    limit: Annotated[int, Query()] = 24,
) -> Response:
    data = await MarketWatchlistService.history_services(
        query_db, symbol, market, limit=limit, user_id=_current_user_id(current_user)
    )
    return ResponseUtil.success(data=data)


@market_controller.post(
    '/watchlist/analyze',
    summary='立即执行自选综合分析',
    description='综合技术指标、长桥资讯与舆情给出建议；不传 symbol 则分析全部启用自选',
    dependencies=[UserInterfaceAuthDependency('market:watchlist:analyze')],
)
@Log(title='行情自选分析', business_type=BusinessType.OTHER)
async def analyze_market_watchlist(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: MarketWatchlistAnalyzeModel = Body(default_factory=MarketWatchlistAnalyzeModel),
) -> Response:
    if not getattr(body, 'symbol', None):
        ticket = await JobQueue.submit(
            'watchlist_analyze',
            {'userId': _current_user_id(current_user), 'refreshContent': getattr(body, 'refresh_content', None)},
        )
        if not ticket:
            raise ServiceException(message='后台任务队列暂不可用，请稍后重试')
        logger.info(f'自选全部分析已入队: {ticket}')
        return ResponseUtil.success(data=ticket, msg='已加入后台队列，稍后刷新清单查看结果')
    data = await MarketWatchlistService.analyze_services(
        query_db, body, user_id=_current_user_id(current_user)
    )
    logger.info(f'自选综合分析完成: {data.get("message")}')
    return ResponseUtil.success(data=data, msg=data.get('message') or '分析完成')


@market_controller.get(
    '/watchlist/backtest',
    summary='自选建议前瞻回测',
    description='对买入/加仓/减仓/卖出建议计算 1/5 个交易日前瞻收益与命中率',
    dependencies=[UserInterfaceAuthDependency('market:watchlist:list')],
)
async def get_market_watchlist_backtest(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    limit: Annotated[int, Query()] = 200,
) -> Response:
    data = await MarketWatchlistService.backtest_services(
        query_db, _current_user_id(current_user), limit=limit
    )
    return ResponseUtil.success(data=data, msg=data.get('message') or '回测完成')


@market_controller.get(
    '/heat/daily',
    summary='分市场每日热度与 Top50',
    description='按 market + tradeDate 返回热度摘要与 Top50 快照；tradeDate 省略则取最近一日。',
    dependencies=[UserInterfaceAuthDependency('market:heat:list')],
)
async def get_market_heat_daily(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    trade_date: Annotated[str | None, Query(alias='tradeDate', description='交易日 YYYY-MM-DD')] = None,
) -> Response:
    data = await MarketHeatService.get_daily_services(query_db, market=market, trade_date=trade_date)
    return ResponseUtil.success(data=data)


@market_controller.get(
    '/heat/trend',
    summary='近几日热度趋势',
    dependencies=[UserInterfaceAuthDependency('market:heat:list')],
)
async def get_market_heat_trend(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    days: Annotated[int, Query(description='近 N 个交易日')] = 5,
) -> Response:
    data = await MarketHeatService.get_trend_services(query_db, market=market, days=days)
    return ResponseUtil.success(data=data)


@market_controller.get(
    '/heat/dates',
    summary='可选历史交易日',
    dependencies=[UserInterfaceAuthDependency('market:heat:list')],
)
async def get_market_heat_dates(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    limit: Annotated[int, Query()] = 30,
) -> Response:
    dates = await MarketHeatService.list_available_dates(query_db, market=market, limit=limit)
    return ResponseUtil.success(data={'market': market.upper(), 'dates': dates})


@market_controller.get(
    '/heat/config',
    summary='热度指标权重配置',
    dependencies=[UserInterfaceAuthDependency('market:heat:list')],
)
async def get_market_heat_config(request: Request) -> Response:
    data = await MarketHeatService.get_config_services()
    return ResponseUtil.success(data=data)


@market_controller.post(
    '/heat/collect',
    summary='手动触发热度采集',
    dependencies=[UserInterfaceAuthDependency('market:heat:collect')],
)
@Log(title='市场热度采集', business_type=BusinessType.OTHER)
async def collect_market_heat(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    trade_date: Annotated[str | None, Query(alias='tradeDate')] = None,
) -> Response:
    ticket = await JobQueue.submit('market_heat_collect', {'market': market.upper(), 'tradeDate': trade_date})
    if ticket:
        return ResponseUtil.success(data=ticket, msg='已加入后台队列')
    data = await MarketHeatService.collect_market(query_db, market=market, trade_date=trade_date)
    return ResponseUtil.success(data=data, msg='采集完成')
