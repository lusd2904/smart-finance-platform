from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from module_quant.service.longbridge_service import LongbridgeService
from module_quant.service.strategy_service import StrategyService
from module_trade.dao.trade_dao import TradeDao
from module_trade.entity.do.trade_do import PlatAutoTradeDecision
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from module_trade.entity.do.trade_do import PlatAiTradeRunLog

# 客户端允许覆盖的非安全字段；限额/纸账户开关只能由服务端决定
_CLIENT_CONFIG_KEYS = frozenset({'max_symbols', 'min_confidence', 'strategy_profile', 'custom_thresholds'})


def merge_runtime_config(custom_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = dict(AutoTradeService.DEFAULT_CONFIG)
    if not custom_config:
        return config
    for key in _CLIENT_CONFIG_KEYS:
        if key in custom_config and custom_config[key] is not None:
            config[key] = custom_config[key]
    config['max_symbols'] = max(1, min(int(config.get('max_symbols') or 3), 20))
    config['min_confidence'] = max(0, min(int(config.get('min_confidence') or 65), 100))
    return config


def resolve_submit_permission(*, execute: bool, trading_enabled: bool, require_paper: bool) -> tuple[bool, str | None]:
    """
    是否允许自动交易真正向券商提交委托。
    纸账户保护开启或交易开关关闭时一律扫描-only。
    """
    if not execute:
        return False, '仅扫描不下单'
    if require_paper:
        return False, '纸账户保护开启，拒绝自动委托（扫描-only）'
    if not trading_enabled:
        return False, '实盘交易开关未开启，拒绝自动委托'
    return True, None


def check_daily_limits(
    today_orders: int,
    max_orders: int,
    today_notional: float,
    max_notional: float,
) -> str | None:
    if today_orders >= max_orders:
        return f'已达日内最大订单数限制 ({today_orders}/{max_orders})'
    if today_notional >= max_notional:
        return f'已达日内名义本金上限 (${today_notional:.2f}/${max_notional:.2f})'
    return None


def slippage_exceeded(signal_price: float, realtime_price: float, tolerance: float) -> bool:
    if realtime_price <= 0:
        return True
    if signal_price <= 0:
        return False
    return abs(realtime_price - signal_price) / signal_price > tolerance


def parse_symbol_market(raw: str, default_market: str = 'US') -> tuple[str, str]:
    text = str(raw or '').strip().upper()
    if '.' in text:
        code, suffix = text.rsplit('.', 1)
        if suffix in {'US', 'HK', 'SH', 'SZ'}:
            market = 'CN' if suffix in {'SH', 'SZ'} else suffix
            return code, market
    return text, (default_market or 'US').upper()


def match_position(positions: list[dict[str, Any]], symbol: str, market: str) -> dict[str, Any] | None:
    lb = LongbridgeService.to_longbridge_symbol(symbol, market).upper()
    candidates = {symbol.upper(), lb, f'{symbol}.{market}'.upper()}
    for pos in positions or []:
        if str(pos.get('symbol') or '').upper() in candidates:
            return pos
    return None


class AutoTradeService:
    """
    自选股 AI 自动交易与日内风控护栏服务。
    默认扫描-only：纸账户保护开启且客户端不能关闭限额。
    """

    DEFAULT_CONFIG = {
        'enabled': True,
        'auto_execute': False,
        'interval': 900,
        'strategy_profile': 'balanced',
        'max_symbols': 3,
        'max_amount_per_symbol': 2000.0,
        'max_daily_orders': 10,
        'max_daily_notional_amount': 6000.0,
        'max_position_ratio': 0.15,
        'min_confidence': 65,
        'require_paper': True,
        'price_slippage_tolerance': 0.03,
    }

    @classmethod
    def _generate_cycle_id(cls) -> str:
        return f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    @classmethod
    async def _today_stats(cls, db: AsyncSession) -> tuple[int, float]:
        today_start = datetime.combine(date.today(), datetime.min.time())
        stmt = select(
            func.count(PlatAutoTradeDecision.decision_id),
            func.sum(PlatAutoTradeDecision.quantity * PlatAutoTradeDecision.price),
        ).where(
            PlatAutoTradeDecision.create_time >= today_start,
            PlatAutoTradeDecision.status.in_(['submitted', 'filled']),
        )
        res = await db.execute(stmt)
        row = res.first()
        return int(row[0] or 0) if row else 0, float(row[1] or 0.0) if row else 0.0

    @classmethod
    def _serialize_log(cls, log: PlatAiTradeRunLog) -> dict[str, Any]:
        return {
            'runId': log.run_id,
            'cycleId': log.cycle_id,
            'source': log.source,
            'strategyProfile': log.strategy_profile,
            'targetCount': log.target_count,
            'evaluatedCount': log.evaluated_count,
            'opportunityCount': log.opportunity_count,
            'submittedOrdersCount': log.submitted_orders_count,
            'status': log.status,
            'message': log.message,
            'startedAt': log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else None,
            'finishedAt': log.finished_at.strftime('%Y-%m-%d %H:%M:%S') if log.finished_at else None,
        }

    @classmethod
    def _serialize_decision(cls, d: PlatAutoTradeDecision) -> dict[str, Any]:
        return {
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
            'orderId': d.order_id,
            'error': d.error,
            'createTime': d.create_time.strftime('%Y-%m-%d %H:%M:%S') if d.create_time else None,
        }

    @classmethod
    async def _resolve_targets(
        cls, db: AsyncSession, symbols: list[str] | list[dict[str, str]] | None
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        if symbols:
            for item in symbols:
                if isinstance(item, dict):
                    sym = str(item.get('symbol') or '').strip()
                    mkt = str(item.get('market') or 'US').strip().upper()
                    if sym:
                        if '.' in sym and not item.get('market'):
                            sym, mkt = parse_symbol_market(sym, mkt)
                        items.append({'symbol': sym, 'market': mkt})
                else:
                    sym, mkt = parse_symbol_market(str(item))
                    if sym:
                        items.append({'symbol': sym, 'market': mkt})
            return items

        from module_quant.dao.quant_dao import QuantWatchlistDao

        rows = await QuantWatchlistDao.get_enabled_symbols(db)
        seen: set[tuple[str, str]] = set()
        for row in rows:
            sym = str(getattr(row, 'symbol', '') or '').strip()
            mkt = str(getattr(row, 'market', '') or 'US').strip().upper()
            if sym:
                if '.' in sym:
                    sym, inferred = parse_symbol_market(sym, mkt)
                    mkt = inferred or mkt
                if (sym, mkt) in seen:
                    continue  # 多账号重复加入同一标的时只扫一次
                seen.add((sym, mkt))
                items.append({'symbol': sym, 'market': mkt})
        return items

    @classmethod
    async def get_status(cls, db: AsyncSession) -> dict[str, Any]:
        await LongbridgeService.ensure_credentials_from_db(db)
        configured = LongbridgeService.is_configured()
        trading_enabled = LongbridgeService.is_trading_enabled()
        today_orders_count, today_notional_amount = await cls._today_stats(db)
        recent_logs = await TradeDao.list_ai_trade_run_logs(db, limit=5)
        recent_decisions = await TradeDao.list_auto_trade_decisions(db, limit=10)
        require_paper = bool(cls.DEFAULT_CONFIG['require_paper'])
        submit_allowed, submit_block_reason = resolve_submit_permission(
            execute=True, trading_enabled=trading_enabled, require_paper=require_paper
        )
        return {
            'configured': configured,
            'message': None if configured else '长桥凭据未配置，自动交易仅提供空状态',
            'tradingEnabled': trading_enabled,
            'submitAllowed': submit_allowed,
            'submitBlockReason': None if submit_allowed else submit_block_reason,
            'config': {
                **cls.DEFAULT_CONFIG,
                'auto_execute': False,
            },
            'guardrails': {
                'todayOrdersCount': today_orders_count,
                'maxDailyOrders': cls.DEFAULT_CONFIG['max_daily_orders'],
                'todayNotionalAmount': round(today_notional_amount, 2),
                'maxDailyNotionalAmount': cls.DEFAULT_CONFIG['max_daily_notional_amount'],
                'requirePaper': require_paper,
                'tradingEnabled': trading_enabled,
                'isOrderLimitReached': today_orders_count >= cls.DEFAULT_CONFIG['max_daily_orders'],
                'isAmountLimitReached': today_notional_amount >= cls.DEFAULT_CONFIG['max_daily_notional_amount'],
            },
            'recentRuns': [cls._serialize_log(log) for log in recent_logs],
            'recentDecisions': [cls._serialize_decision(d) for d in recent_decisions],
        }

    @classmethod
    async def run_watchlist_strategy_cycle(  # noqa: PLR0912, PLR0915
        cls,
        db: AsyncSession,
        symbols: list[str] | list[dict[str, str]] | None = None,
        source: str = 'manual',
        execute: bool | None = None,
        strategy_profile: str = 'balanced',
        custom_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cycle_id = cls._generate_cycle_id()
        started_at = datetime.now()
        config = merge_runtime_config(custom_config)
        if strategy_profile:
            config['strategy_profile'] = strategy_profile

        await LongbridgeService.ensure_credentials_from_db(db)
        target_items = await cls._resolve_targets(db, symbols)

        logger.info(
            f'[AI自动交易] 启动扫描 cycle_id={cycle_id}, 标的数={len(target_items)}, source={source}, execute={execute}'
        )

        if not target_items:
            summary_msg = '自选池为空，已跳过扫描。请先在量化自选池中添加标的。'
            finished_at = datetime.now()
            await TradeDao.add_ai_trade_run_log(
                db,
                {
                    'cycle_id': cycle_id,
                    'source': source,
                    'strategy_profile': config.get('strategy_profile', 'balanced'),
                    'target_count': 0,
                    'evaluated_count': 0,
                    'opportunity_count': 0,
                    'submitted_orders_count': 0,
                    'status': 'skipped',
                    'message': summary_msg,
                    'started_at': started_at,
                    'finished_at': finished_at,
                },
            )
            await db.commit()
            return {
                'ok': True,
                'cycleId': cycle_id,
                'source': source,
                'submittedOrdersCount': 0,
                'message': summary_msg,
                'candidates': [],
                'opportunities': [],
                'skippedReasons': [{'symbol': '*', 'reason': summary_msg}],
            }

        scan_res = await StrategyService.run_strategy_cycle_async(
            symbols=target_items,
            profile=config.get('strategy_profile', 'balanced'),
            custom_config=config.get('custom_thresholds'),
        )
        scan_results = scan_res.get('signals', []) if isinstance(scan_res, dict) else (scan_res or [])

        candidates = []
        opportunities = []
        skipped_reasons: list[dict[str, str]] = []
        min_confidence = int(config.get('min_confidence', 65))

        for item in scan_results:
            decision = item.get('signal', 'HOLD')
            confidence = int(item.get('confidence', 50))
            score_val = item.get('score', 0)
            metrics = ((item.get('factor_json') or {}).get('metrics') or {})
            price = item.get('price') or metrics.get('latestClose')
            is_opp = decision in {'BUY', 'SELL'} and confidence >= min_confidence
            candidate_record = {
                'symbol': item.get('symbol'),
                'market': item.get('market', 'US'),
                'price': price,
                'signal': decision,
                'confidence': confidence,
                'reason': item.get('reason'),
                'isOpportunity': is_opp,
                'score': {'total': score_val},
                'factors': item.get('factor_json'),
            }
            candidates.append(candidate_record)
            if is_opp:
                opportunities.append(candidate_record)

        opportunities.sort(
            key=lambda x: (x.get('confidence', 0), float((x.get('score') or {}).get('total', 0))),
            reverse=True,
        )

        should_execute = bool(execute) if execute is not None else bool(config.get('auto_execute', False))
        trading_enabled = LongbridgeService.is_trading_enabled()
        can_submit, submit_block = resolve_submit_permission(
            execute=should_execute,
            trading_enabled=trading_enabled,
            require_paper=bool(config.get('require_paper', True)),
        )

        today_orders_count, today_notional_amount = await cls._today_stats(db)
        guardrail_snapshot = {
            'todayOrdersCount': today_orders_count,
            'maxDailyOrders': config['max_daily_orders'],
            'todayNotionalAmount': round(today_notional_amount, 2),
            'maxDailyNotionalAmount': config['max_daily_notional_amount'],
            'maxSymbols': config['max_symbols'],
            'maxAmountPerSymbol': config['max_amount_per_symbol'],
            'requirePaper': config['require_paper'],
            'tradingEnabled': trading_enabled,
            'submitAllowed': can_submit,
            'submitBlockReason': submit_block,
            'priceSlippageTolerance': config['price_slippage_tolerance'],
        }

        submitted_decisions: list[dict[str, Any]] = []
        submitted_count = 0
        positions: list[dict[str, Any]] = []
        net_assets = 0.0

        if can_submit and opportunities:
            pos_res = await LongbridgeService.get_positions_async()
            positions = pos_res.get('positions') or []
            acc = LongbridgeService.flatten_account(await LongbridgeService.get_account_balance_async())
            net_assets = float(acc.get('netAssets') or 0)

            for opp in opportunities[: config['max_symbols']]:
                symbol = str(opp.get('symbol') or '')
                market = str(opp.get('market') or 'US')
                side = str(opp.get('signal') or 'HOLD').upper()
                signal_price = float(opp.get('price') or 0.0)

                limit_reason = check_daily_limits(
                    today_orders_count,
                    int(config['max_daily_orders']),
                    today_notional_amount,
                    float(config['max_daily_notional_amount']),
                )
                if limit_reason:
                    skipped_reasons.append({'symbol': symbol, 'reason': limit_reason})
                    continue

                quote = await LongbridgeService.get_realtime_quote_async(symbol, market)
                realtime_price = LongbridgeService.extract_last_price(quote, symbol)
                if realtime_price <= 0:
                    skipped_reasons.append(
                        {'symbol': symbol, 'reason': '未能获取券商有效盘中实时报价，为防滑点拒绝下单'}
                    )
                    continue

                if slippage_exceeded(signal_price, realtime_price, float(config['price_slippage_tolerance'])):
                    skipped_reasons.append(
                        {
                            'symbol': symbol,
                            'reason': (
                                f'实时价 {realtime_price} 与信号价 {signal_price} 偏离过大 '
                                f'({abs(realtime_price - signal_price) / max(signal_price, 1e-9) * 100:.2f}% '
                                f'> {float(config["price_slippage_tolerance"]) * 100:.1f}%)'
                            ),
                        }
                    )
                    continue

                if side == 'SELL':
                    pos = match_position(positions, symbol, market)
                    quantity = int(pos.get('availableQuantity') or pos.get('quantity') or 0) if pos else 0
                    if quantity <= 0:
                        skipped_reasons.append({'symbol': symbol, 'reason': '无可用持仓，跳过卖出'})
                        continue
                else:
                    remaining = float(config['max_daily_notional_amount']) - today_notional_amount
                    target_amount = min(float(config['max_amount_per_symbol']), remaining)
                    if net_assets > 0:
                        cap_by_ratio = net_assets * float(config['max_position_ratio'])
                        target_amount = min(target_amount, cap_by_ratio)
                    if target_amount < 50:
                        skipped_reasons.append(
                            {'symbol': symbol, 'reason': f'剩余可用日内额度不足 (${target_amount:.2f})'}
                        )
                        continue
                    quantity = max(1, int(target_amount / realtime_price))

                order_amount = quantity * realtime_price
                order_res = await LongbridgeService.submit_order_async(
                    symbol=symbol,
                    side=side,
                    order_type='LO',
                    quantity=quantity,
                    price=realtime_price,
                    market=market,
                )
                ok = bool(order_res.get('ok'))
                status = 'submitted' if ok else 'rejected'
                order_id = LongbridgeService.extract_order_id(order_res)
                error_msg = None if ok else (order_res.get('message') or '下单失败')

                decision_dict = {
                    'cycle_id': cycle_id,
                    'symbol': symbol,
                    'market': market,
                    'side': side,
                    'quantity': quantity,
                    'price': realtime_price,
                    'confidence': opp.get('confidence'),
                    'status': status,
                    'reason': opp.get('reason'),
                    'source': source,
                    'order_id': order_id,
                    'error': error_msg,
                }
                await TradeDao.add_auto_trade_decision(db, decision_dict)
                submitted_decisions.append(decision_dict)
                if ok:
                    submitted_count += 1
                    today_orders_count += 1
                    today_notional_amount += order_amount
        elif should_execute and not can_submit and submit_block:
            skipped_reasons.append({'symbol': '*', 'reason': submit_block})

        finished_at = datetime.now()
        duration = round((finished_at - started_at).total_seconds(), 2)
        summary_msg = (
            f'扫描完成耗时 {duration}s，评估 {len(candidates)} 标的，发现 {len(opportunities)} 机会，'
            f'执行委托 {submitted_count} 笔'
        )
        if submit_block and should_execute:
            summary_msg += f'；{submit_block}'

        await TradeDao.add_ai_trade_run_log(
            db,
            {
                'cycle_id': cycle_id,
                'source': source,
                'strategy_profile': config.get('strategy_profile', 'balanced'),
                'target_count': len(target_items),
                'evaluated_count': len(candidates),
                'opportunity_count': len(opportunities),
                'submitted_orders_count': submitted_count,
                'status': 'completed',
                'guardrail_snapshot': json.dumps(guardrail_snapshot, ensure_ascii=False),
                'candidates_snapshot': json.dumps(candidates, ensure_ascii=False, default=str),
                'opportunities_snapshot': json.dumps(opportunities, ensure_ascii=False, default=str),
                'skipped_reasons': json.dumps(skipped_reasons, ensure_ascii=False),
                'message': summary_msg,
                'started_at': started_at,
                'finished_at': finished_at,
            },
        )
        await db.commit()

        return {
            'ok': True,
            'cycleId': cycle_id,
            'source': source,
            'strategyProfile': config.get('strategy_profile', 'balanced'),
            'targetCount': len(target_items),
            'evaluatedCount': len(candidates),
            'opportunityCount': len(opportunities),
            'submittedOrdersCount': submitted_count,
            'submitAllowed': can_submit,
            'guardrailSnapshot': guardrail_snapshot,
            'candidates': candidates,
            'opportunities': opportunities,
            'skippedReasons': skipped_reasons,
            'submittedDecisions': submitted_decisions,
            'message': summary_msg,
            'durationSeconds': duration,
        }
