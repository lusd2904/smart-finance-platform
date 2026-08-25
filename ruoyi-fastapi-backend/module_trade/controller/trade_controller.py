import json
from typing import Annotated

from fastapi import Body, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.log_annotation import Log
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.entity.vo.user_vo import CurrentUserModel
from common.enums import BusinessType
from common.router import APIRouterPro
from module_trade.dao.trade_dao import TradeDao
from module_trade.service.platform_ext_service import PlatformExtService
from module_trade.service.trade_service import TradeService
from utils.log_util import logger
from utils.response_util import ResponseUtil

trade_controller = APIRouterPro(
    prefix='/trade', order_num=33, tags=['交易中心'], dependencies=[PreAuthDependency()]
)


def _current_user_id(current_user: CurrentUserModel) -> int:
    user = current_user.user if current_user else None
    user_id = getattr(user, 'user_id', None) if user else None
    from exceptions.exception import ServiceException

    if not user_id:
        raise ServiceException(message='无法识别当前用户')
    return int(user_id)


@trade_controller.get(
    '/account',
    summary='账户资金',
    dependencies=[UserInterfaceAuthDependency('trade:account:list')],
)
async def trade_account(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await TradeService.get_account_services(query_db)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/positions',
    summary='持仓列表',
    dependencies=[UserInterfaceAuthDependency('trade:position:list')],
)
async def trade_positions(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await TradeService.get_positions_services(query_db)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/orders',
    summary='订单列表',
    dependencies=[UserInterfaceAuthDependency('trade:order:list')],
)
async def trade_orders(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    scope: Annotated[str, Query(description='today|history')] = 'today',
) -> Response:
    data = await TradeService.get_orders_services(query_db, scope=scope)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/order/{order_id}',
    summary='单笔订单状态',
    description='在今日与历史委托中查找，返回最新状态/成交量',
    dependencies=[UserInterfaceAuthDependency('trade:order:list')],
)
async def trade_order_detail(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    order_id: Annotated[str, Path(description='长桥订单号')],
) -> Response:
    data = await TradeService.get_order_services(query_db, order_id)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/quote/depth',
    summary='标的买卖盘',
    description='长桥 QuoteContext.depth；A股返回空盘口提示，不补造档位',
    dependencies=[UserInterfaceAuthDependency('trade:account:list')],
)
async def trade_quote_depth(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
) -> Response:
    data = await TradeService.get_depth_services(query_db, symbol=symbol, market=market)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/quote/trades',
    summary='标的成交明细',
    description='长桥 QuoteContext.trades；A股返回空列表提示',
    dependencies=[UserInterfaceAuthDependency('trade:account:list')],
)
async def trade_quote_trades(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    count: Annotated[int, Query(description='条数 1-100')] = 30,
) -> Response:
    data = await TradeService.get_trades_services(query_db, symbol=symbol, market=market, count=count)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/quote/snapshot',
    summary='标的行情快照（长桥补缺）',
    description='quote + static_info + calc_indexes + 资金分布 + 52周 + 资讯标题。库里已有字段由前端保留，本接口补估值/换手/量比/市值等缺口。缓存约 60 秒。',
    dependencies=[UserInterfaceAuthDependency('trade:account:list')],
)
async def trade_quote_snapshot(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
) -> Response:
    data = await TradeService.get_quote_snapshot_services(query_db, symbol=symbol, market=market)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/quote/kline',
    summary='交易台K线',
    description='Influx 日K/周K/月K；US/HK 分钟与分时在时序库为空时回退长桥 candlesticks/intraday',
    dependencies=[UserInterfaceAuthDependency('trade:account:list')],
)
async def trade_quote_kline(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    symbol: Annotated[str, Query(description='标的代码')],
    market: Annotated[str, Query(description='市场 US/HK/CN')] = 'US',
    period: Annotated[str, Query(description='intraday/1min/5min/15min/daily/weekly/monthly')] = 'daily',
    limit: Annotated[int, Query(description='K线条数')] = 200,
) -> Response:
    data = await TradeService.get_quote_kline_services(
        query_db, symbol=symbol, market=market, period=period, limit=limit
    )
    return ResponseUtil.success(data=data)


@trade_controller.post(
    '/order',
    summary='提交订单',
    dependencies=[UserInterfaceAuthDependency('trade:order:submit')],
)
@Log(title='交易下单', business_type=BusinessType.INSERT)
async def trade_submit(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict, Body()],
) -> Response:
    result = await TradeService.submit_order_services(
        query_db,
        symbol=str(body.get('symbol') or ''),
        side=str(body.get('side') or 'buy'),
        quantity=float(body.get('quantity') or 0),
        order_type=str(body.get('orderType') or 'LO'),
        price=float(body['price']) if body.get('price') not in (None, '') else None,
        market=str(body.get('market') or 'US'),
    )
    logger.info(f'下单结果: {result}')
    return ResponseUtil.success(data=result, msg=result.get('message') or '')


@trade_controller.post(
    '/order/{order_id}/cancel',
    summary='撤单',
    dependencies=[UserInterfaceAuthDependency('trade:order:cancel')],
)
@Log(title='交易撤单', business_type=BusinessType.UPDATE)
async def trade_cancel(
    request: Request,
    order_id: Annotated[str, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    result = await TradeService.cancel_order_services(query_db, order_id)
    return ResponseUtil.success(data=result, msg=result.get('message') or '')


@trade_controller.get(
    '/notifications',
    summary='通知列表',
    dependencies=[UserInterfaceAuthDependency('trade:notice:list')],
)
async def trade_notifications(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: Annotated[int, Query()] = 50,
) -> Response:
    data = await TradeService.list_notifications_services(query_db, limit=limit)
    return ResponseUtil.success(data=data)


@trade_controller.post(
    '/notifications/read',
    summary='标记通知已读',
    dependencies=[UserInterfaceAuthDependency('trade:notice:list')],
)
async def trade_notifications_read(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    body = body or {}
    notice_id = body.get('id')
    data = await TradeService.mark_notification_read_services(query_db, int(notice_id) if notice_id else None)
    return ResponseUtil.success(data=data)


@trade_controller.post(
    '/backtest/run',
    summary='运行简易回测',
    dependencies=[UserInterfaceAuthDependency('trade:backtest:run')],
)
@Log(title='策略回测', business_type=BusinessType.OTHER)
async def trade_backtest_run(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict, Body()],
) -> Response:
    data = await TradeService.run_backtest_services(
        query_db,
        symbol=str(body.get('symbol') or 'AAPL'),
        market=str(body.get('market') or 'US'),
        days=int(body.get('days') or 120),
    )
    return ResponseUtil.success(data=data, msg=data.get('message') or '')


@trade_controller.get(
    '/backtest/list',
    summary='回测历史',
    dependencies=[UserInterfaceAuthDependency('trade:backtest:list')],
)
async def trade_backtest_list(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await TradeService.list_backtests_services(query_db)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/backtest/{run_id}',
    summary='回测详情',
    dependencies=[UserInterfaceAuthDependency('trade:backtest:list')],
)
async def trade_backtest_detail(
    request: Request,
    run_id: Annotated[int, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await TradeService.get_backtest_services(query_db, run_id)
    return ResponseUtil.success(data=data)


from module_trade.service.auto_trade_service import AutoTradeService  # noqa: E402


@trade_controller.get(
    '/auto/status',
    summary='获取AI自动交易状态与日内护栏',
    dependencies=[UserInterfaceAuthDependency(['trade:aitrade:list', 'quant:strategy:list', 'quant:dailylist:list'])],
)
async def auto_trade_status(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    try:
        data = await AutoTradeService.get_status(query_db, user_id=_current_user_id(current_user))
    except Exception as exc:
        logger.exception('[自动交易] status 读取失败')
        data = {
            'configured': False,
            'message': f'自动交易状态读取失败: {exc}',
            'tradingEnabled': False,
            'submitAllowed': False,
            'submitBlockReason': str(exc),
            'recentRuns': [],
            'recentDecisions': [],
            'guardrails': {
                'tradingEnabled': True,
                'todayOrdersCount': 0,
                'maxDailyOrders': 10,
                'todayNotionalAmount': 0,
                'maxDailyNotionalAmount': 6000,
            },
        }
    return ResponseUtil.success(data=data)


@trade_controller.put(
    '/auto/settings',
    summary='保存当前账户自动交易开关',
    dependencies=[UserInterfaceAuthDependency(['trade:aitrade:run', 'quant:strategy:list'])],
)
async def auto_trade_save_settings(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    body = body or {}
    settings = await AutoTradeService.save_user_trade_settings(
        query_db,
        _current_user_id(current_user),
        auto_trade_enabled=bool(body.get('autoTradeEnabled') or body.get('auto_trade_enabled')),
        daily_buy_ratio=body.get('dailyBuyRatio', body.get('daily_buy_ratio')),
        max_symbol_position_pct=body.get('maxSymbolPositionPct', body.get('max_symbol_position_pct')),
    )
    data = await AutoTradeService.get_status(query_db, user_id=settings['user_id'])
    return ResponseUtil.success(data=data, msg='已保存本账户自动交易设置')


@trade_controller.post(
    '/auto/run',
    summary='手动触发自选池AI自动交易扫描',
    dependencies=[UserInterfaceAuthDependency('trade:aitrade:run')],
)
@Log(
    title='AI自动交易扫描',
    business_type=BusinessType.OTHER,
    request_log_mode='summary',
    response_log_mode='summary',
)
async def auto_trade_run(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    body = body or {}
    try:
        data = await AutoTradeService.run_watchlist_strategy_cycle(
            query_db,
            symbols=body.get('symbols'),
            source='manual_api',
            execute=bool(body.get('execute')),
            strategy_profile=body.get('strategyProfile', 'balanced'),
            custom_config=body.get('customConfig') if isinstance(body.get('customConfig'), dict) else None,
            user_id=_current_user_id(current_user),
        )
    except Exception as exc:
        logger.exception('[自动交易] run 失败')
        return ResponseUtil.failure(msg=f'自动交易扫描失败: {exc}')
    return ResponseUtil.success(data=data, msg=data.get('message', '扫描完成'))


@trade_controller.get(
    '/ai-trade-runs',
    summary='AI自动交易台账列表',
    dependencies=[UserInterfaceAuthDependency('trade:aitrade:list')],
)
async def trade_ai_runs(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    limit: Annotated[int, Query()] = 30,
) -> Response:
    logs = await TradeDao.list_ai_trade_run_logs(query_db, limit=limit, user_id=_current_user_id(current_user))
    res = [
        {
            'runId': log.run_id,
            'cycleId': log.cycle_id,
            'userId': getattr(log, 'user_id', None),
            'source': log.source,
            'strategyProfile': log.strategy_profile,
            'targetCount': log.target_count,
            'evaluatedCount': log.evaluated_count,
            'opportunityCount': log.opportunity_count,
            'submittedOrdersCount': log.submitted_orders_count,
            'status': log.status,
            'guardrailSnapshot': json.loads(log.guardrail_snapshot) if log.guardrail_snapshot else {},
            'candidatesSnapshot': json.loads(log.candidates_snapshot) if log.candidates_snapshot else [],
            'opportunitiesSnapshot': json.loads(log.opportunities_snapshot) if log.opportunities_snapshot else [],
            'skippedReasons': json.loads(log.skipped_reasons) if log.skipped_reasons else [],
            'message': log.message,
            'startedAt': log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else None,
            'finishedAt': log.finished_at.strftime('%Y-%m-%d %H:%M:%S') if log.finished_at else None,
        }
        for log in logs
    ]
    return ResponseUtil.success(data=res)


@trade_controller.get(
    '/auto/decisions',
    summary='AI自动交易决策明细',
    dependencies=[UserInterfaceAuthDependency('trade:aitrade:list')],
)
async def trade_auto_decisions(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    cycle_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
) -> Response:
    decisions = await TradeDao.list_auto_trade_decisions(query_db, limit=limit, cycle_id=cycle_id)
    res = [
        {
            'decisionId': d.decision_id,
            'cycleId': d.cycle_id,
            'symbol': d.symbol,
            'market': d.market,
            'side': d.side,
            'quantity': d.quantity,
            'price': float(d.price) if d.price else None,
            'confidence': d.confidence,
            'status': d.status,
            'reason': d.reason,
            'source': d.source,
            'orderId': d.order_id,
            'error': d.error,
            'createTime': d.create_time.strftime('%Y-%m-%d %H:%M:%S') if d.create_time else None,
        }
        for d in decisions
    ]
    return ResponseUtil.success(data=res)


# ---------------- 平台加深：覆盖/策略配置/风控/批量AI/持久通知 ----------------


@trade_controller.get(
    '/coverage',
    summary='行情历史覆盖率',
    dependencies=[UserInterfaceAuthDependency('market:kline:list')],
)
async def history_coverage(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PlatformExtService.history_coverage(query_db)
    return ResponseUtil.success(data=data)


@trade_controller.get(
    '/strategy-profiles',
    summary='策略配置档位列表',
    dependencies=[UserInterfaceAuthDependency('quant:strategy:list')],
)
async def strategy_profiles(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    return ResponseUtil.success(
        data=await PlatformExtService.list_strategy_profiles(query_db, _current_user_id(current_user))
    )


@trade_controller.put(
    '/strategy-profiles/{code}',
    summary='保存当前账户策略配置档位',
    dependencies=[UserInterfaceAuthDependency('quant:strategy:list')],
)
@Log(title='策略配置', business_type=BusinessType.UPDATE)
async def save_strategy_profile(
    request: Request,
    code: Annotated[str, Path()],
    body: Annotated[dict, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    await PlatformExtService.save_strategy_profile(
        query_db,
        code=code,
        name=str(body.get('profileName') or code),
        config=body.get('config') or body,
        user_id=_current_user_id(current_user),
    )
    return ResponseUtil.success(msg='已保存本账户策略档位')


@trade_controller.get(
    '/risk/rules',
    summary='风控规则列表',
    dependencies=[UserInterfaceAuthDependency('trade:risk:list')],
)
async def risk_rules(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PlatformExtService.list_risk_rules(query_db))


@trade_controller.post(
    '/risk/rules',
    summary='保存风控规则',
    dependencies=[UserInterfaceAuthDependency('trade:risk:edit')],
)
@Log(title='风控规则', business_type=BusinessType.UPDATE)
async def save_risk_rule(
    request: Request,
    body: Annotated[dict, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    rid = await PlatformExtService.save_risk_rule(query_db, body)
    return ResponseUtil.success(data={'ruleId': rid}, msg='保存成功')


@trade_controller.delete(
    '/risk/rules/{rule_id}',
    summary='删除风控规则',
    dependencies=[UserInterfaceAuthDependency('trade:risk:edit')],
)
@Log(title='风控规则', business_type=BusinessType.DELETE)
async def delete_risk_rule(
    request: Request,
    rule_id: Annotated[int, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    await PlatformExtService.delete_risk_rule(query_db, rule_id)
    return ResponseUtil.success(msg='删除成功')


@trade_controller.get(
    '/risk/events',
    summary='风控事件列表',
    dependencies=[UserInterfaceAuthDependency('trade:risk:list')],
)
async def risk_events(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: Annotated[int, Query()] = 50,
    status: Annotated[str | None, Query()] = None,
) -> Response:
    try:
        data = await PlatformExtService.list_risk_events(query_db, limit, status=status)
    except Exception as exc:
        logger.warning(f'[风控事件] API 降级空状态: {exc}')
        data = []
    return ResponseUtil.success(data=data)


@trade_controller.post(
    '/risk/evaluate',
    summary='执行风控扫描',
    dependencies=[UserInterfaceAuthDependency('trade:risk:edit')],
)
@Log(title='风控扫描', business_type=BusinessType.OTHER)
async def risk_evaluate(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    data = await PlatformExtService.evaluate_risk(query_db)
    return ResponseUtil.success(data=data, msg=f"生成 {data.get('created', 0)} 条事件")


@trade_controller.put(
    '/risk/events/{event_id}/status',
    summary='更新风控事件状态',
    dependencies=[UserInterfaceAuthDependency('trade:risk:edit')],
)
@Log(title='风控事件处理', business_type=BusinessType.UPDATE)
async def update_risk_event_status(
    request: Request,
    event_id: Annotated[int, Path()],
    body: Annotated[dict, Body()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    operator = None
    if current_user.user is not None:
        operator = current_user.user.user_name
    data = await PlatformExtService.update_risk_event_review(
        query_db, event_id, body or {}, operator=operator
    )
    return ResponseUtil.success(data=data, msg='更新风控状态成功')


@trade_controller.get(
    '/notices',
    summary='持久化通知列表',
    dependencies=[UserInterfaceAuthDependency('trade:notice:list')],
)
async def notices_db(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    limit: Annotated[int, Query()] = 50,
) -> Response:
    return ResponseUtil.success(data=await PlatformExtService.list_notices_db(query_db, limit))


@trade_controller.post(
    '/notices/read',
    summary='持久化通知已读',
    dependencies=[UserInterfaceAuthDependency('trade:notice:list')],
)
async def notices_read_db(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    body = body or {}
    nid = body.get('id')
    await PlatformExtService.mark_notice_read_db(query_db, int(nid) if nid else None)
    return ResponseUtil.success(msg='ok')


@trade_controller.post(
    '/ai/batch',
    summary='批量AI研判',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
@Log(title='批量AI研判', business_type=BusinessType.OTHER)
async def ai_batch_run(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    body = body or {}
    symbols = body.get('symbols')
    data = await PlatformExtService.run_ai_batch(
        query_db,
        symbols=symbols,
        market=str(body.get('market') or 'US'),
        days=int(body.get('days') or 90),
    )
    return ResponseUtil.success(data=data, msg=f"完成 {data.get('success')}/{data.get('total')}")


@trade_controller.get(
    '/ai/batches',
    summary='批量AI历史',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
async def ai_batches(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PlatformExtService.list_ai_batches(query_db))


@trade_controller.get(
    '/ai/batches/{batch_id}/items',
    summary='批量AI明细',
    dependencies=[UserInterfaceAuthDependency('market:ai:analyze')],
)
async def ai_batch_items(
    request: Request,
    batch_id: Annotated[int, Path()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(data=await PlatformExtService.list_ai_batch_items(query_db, batch_id))


@trade_controller.get(
    '/feishu/config',
    summary='飞书推送订阅',
    dependencies=[UserInterfaceAuthDependency('trade:feishu:query')],
)
async def get_feishu_config(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    from module_trade.service.feishu_push_service import (
        FeishuPushService,
    )

    user = current_user.user if current_user else None
    user_id = int(getattr(user, 'user_id', 0) or 0)
    return ResponseUtil.success(data=await FeishuPushService.get_config(query_db, user_id))


@trade_controller.put(
    '/feishu/config',
    summary='保存飞书推送订阅',
    dependencies=[UserInterfaceAuthDependency('trade:feishu:edit')],
)
@Log(title='飞书推送订阅', business_type=BusinessType.UPDATE)
async def put_feishu_config(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    from module_trade.service.feishu_push_service import (
        FeishuPushService,
    )

    user = current_user.user if current_user else None
    user_id = int(getattr(user, 'user_id', 0) or 0)
    data = await FeishuPushService.save_config(query_db, user_id, body or {})
    return ResponseUtil.success(data=data, msg='订阅已保存')


@trade_controller.post(
    '/feishu/test',
    summary='发送飞书测试卡片',
    dependencies=[UserInterfaceAuthDependency('trade:feishu:test')],
)
@Log(title='飞书测试推送', business_type=BusinessType.OTHER)
async def test_feishu(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    body: Annotated[dict | None, Body()] = None,
) -> Response:
    from module_trade.service.feishu_push_service import (
        FeishuPushService,
    )

    user = current_user.user if current_user else None
    user_id = int(getattr(user, 'user_id', 0) or 0)
    data = await FeishuPushService.test_push(query_db, user_id, str((body or {}).get('channel') or 'personal'))
    return ResponseUtil.success(data=data, msg=data.get('message') or '已发送')
