from __future__ import annotations

import json
import math
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

# 客户端允许覆盖的非安全字段；日内限额只能由服务端决定
_CLIENT_CONFIG_KEYS = frozenset({'max_symbols', 'min_confidence', 'strategy_profile', 'custom_thresholds'})
MIN_TARGET_AMOUNT_USD = 50
DAILY_BUY_POSITION_RATIO = 0.20
DEFAULT_MAX_SYMBOL_POSITION_PCT = 0.10
# 默认策略：美/港热度池（不含 A 股）；总持仓不超过净资产；已持仓不再加仓
AUTO_TRADE_MARKETS = frozenset({'US', 'HK'})
MAX_GROSS_EXPOSURE_PCT = 1.0
TODAY_BUY_STATUSES = frozenset({'submitted', 'filled', 'pending'})


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


def resolve_submit_permission(
    *,
    execute: bool,
    configured: bool = True,
    auto_trade_enabled: bool = False,
) -> tuple[bool, str | None]:
    """
    是否允许向当前账户的长桥提交委托。
    必须：本次要下单 + 凭据齐全 + 该账户自动交易开关已打开。
    """
    if not execute:
        return False, '仅扫描不下单'
    if not configured:
        return False, '长桥凭据未配置，已跳过委托'
    if not auto_trade_enabled:
        return False, '当前账户未开启自动交易，已跳过委托'
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


def round_limit_price(price: float, market: str = 'US') -> float:
    """按市场最小变动单位取整，避免长桥 602035。"""
    from decimal import ROUND_HALF_UP, Decimal

    p = float(price or 0)
    if p <= 0:
        return p
    mkt = (market or 'US').upper()
    if mkt == 'HK':
        tick = '0.001' if p < 1 else '0.01'
    elif p < 1:
        tick = '0.0001'
    else:
        tick = '0.01'
    tick_d = Decimal(tick)
    price_d = Decimal(str(p))
    steps = (price_d / tick_d).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return float(steps * tick_d)


def daily_buy_cap(net_assets: float, ratio: float = DAILY_BUY_POSITION_RATIO) -> float:
    """日内买入上限 = 账户净资产 × 仓位比例（默认 20%）。"""
    assets = max(0.0, float(net_assets or 0))
    return round(assets * float(ratio), 2)


def clamp_max_symbol_position_pct(pct: float | None) -> float:
    try:
        value = float(pct)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = DEFAULT_MAX_SYMBOL_POSITION_PCT
    if math.isnan(value):
        value = DEFAULT_MAX_SYMBOL_POSITION_PCT
    return max(0.05, min(0.30, value))


def symbol_position_cap(net_assets: float, pct: float | None = None) -> float:
    """单标的持仓市值上限 = 净资产 × 单票仓位比例（默认 10%）。"""
    assets = max(0.0, float(net_assets or 0))
    return round(assets * clamp_max_symbol_position_pct(pct), 2)


def existing_position_market_value(pos: dict[str, Any] | None, last_price: float = 0.0) -> float:  # noqa: PLR0912
    """持仓市值：marketValue → 数量×最新价 → 数量×成本。"""
    if not pos:
        return 0.0
    for key in ('marketValue', 'market_value'):
        raw = pos.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    qty = 0.0
    for key in ('quantity', 'availableQuantity', 'available_quantity'):
        try:
            qty = float(pos.get(key) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty > 0:
            break
    if qty <= 0:
        return 0.0
    last = float(last_price or 0)
    if last > 0:
        return qty * last
    for key in ('costPrice', 'cost_price'):
        try:
            cost = float(pos.get(key) or 0)
        except (TypeError, ValueError):
            cost = 0.0
        if cost > 0:
            return qty * cost
    return 0.0


def symbol_buy_room(net_assets: float, pct: float | None, existing_mv: float) -> float:
    try:
        held = float(existing_mv or 0)
    except (TypeError, ValueError):
        held = 0.0
    return round(symbol_position_cap(net_assets, pct) - max(0.0, held), 2)


def is_auto_trade_market(market: str | None, symbol: str | None = None) -> bool:
    """自动交易只扫美股/港股，A 股（CN/SH/SZ）不扫描、不下单。"""
    from module_quant.service.longbridge_quote import is_cn_market

    if is_cn_market(market, symbol):
        return False
    mkt = str(market or 'US').strip().upper()
    if mkt in {'CN', 'SH', 'SZ', 'A'}:
        return False
    return mkt in AUTO_TRADE_MARKETS or mkt == ''


def should_skip_duplicate_buy(symbol: str, today_bought: set[str] | None) -> bool:
    code, _ = parse_symbol_market(symbol)
    if not code:
        return False
    bought = {parse_symbol_market(item)[0] for item in (today_bought or set())}
    return code in bought


def position_quantity(pos: dict[str, Any] | None) -> float:
    if not pos:
        return 0.0
    for key in ('availableQuantity', 'available_quantity', 'quantity', 'qty'):
        try:
            qty = float(pos.get(key) or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty > 0:
            return qty
    return 0.0


def should_skip_held_buy(pos: dict[str, Any] | None) -> bool:
    """已有持仓则不再买入同一标的（默认策略：不重复买）。"""
    return position_quantity(pos) > 0


def total_position_market_value(positions: list[dict[str, Any]] | None) -> float:
    total = 0.0
    for pos in positions or []:
        total += existing_position_market_value(pos)
    return round(total, 2)


def remaining_gross_room(net_assets: float, total_mv: float, max_pct: float = MAX_GROSS_EXPOSURE_PCT) -> float:
    """总持仓相对净资产的剩余额度；默认不得超过 100% 净资产。"""
    cap = max(0.0, float(net_assets or 0)) * max(0.0, float(max_pct or 0))
    held = max(0.0, float(total_mv or 0))
    return round(cap - held, 2)


def pick_available_cash(account_result: dict[str, Any] | None) -> float:
    balances = (account_result or {}).get('balances') or []
    if not balances:
        flat = LongbridgeService.flatten_account(account_result or {})
        return float(flat.get('availableCash') or flat.get('totalCash') or 0)
    usd = next((b for b in balances if str(b.get('currency') or '').upper() == 'USD'), None)
    chosen = usd or max(
        balances,
        key=lambda b: float(b.get('availableCash') or b.get('totalCash') or 0),
    )
    return float(chosen.get('availableCash') or chosen.get('totalCash') or 0)


def pick_net_assets(account_result: dict[str, Any] | None) -> float:
    """优先用美元净资产，否则取各币种里净资产最大的一档。"""
    balances = (account_result or {}).get('balances') or []
    if not balances:
        flat = LongbridgeService.flatten_account(account_result or {})
        return float(flat.get('netAssets') or 0)
    usd = next((b for b in balances if str(b.get('currency') or '').upper() == 'USD'), None)
    chosen = usd or max(balances, key=lambda b: float(b.get('netAssets') or 0))
    return float(chosen.get('netAssets') or chosen.get('availableCash') or 0)


def slim_scan_row(item: dict[str, Any]) -> dict[str, Any]:
    """台账/接口只保留摘要，去掉 factor_json，避免 TEXT 列溢出。"""
    score = item.get('score')
    if not isinstance(score, dict):
        score = {'total': score}
    return {
        'symbol': item.get('symbol'),
        'market': item.get('market', 'US'),
        'price': item.get('price'),
        'signal': item.get('signal'),
        'confidence': item.get('confidence'),
        'reason': item.get('reason'),
        'isOpportunity': bool(item.get('isOpportunity')),
        'score': score,
    }


def parse_symbol_market(raw: str, default_market: str = 'US') -> tuple[str, str]:
    text = str(raw or '').strip().upper()
    if '.' in text:
        code, suffix = text.rsplit('.', 1)
        if suffix in {'US', 'HK', 'SH', 'SZ'}:
            market = 'CN' if suffix in {'SH', 'SZ'} else suffix
            return code, market
    return text, (default_market or 'US').upper()


def match_position(positions: list[dict[str, Any]], symbol: str, market: str) -> dict[str, Any] | None:
    from module_quant.service.longbridge_quote import _symbol_match_keys

    lb = LongbridgeService.to_longbridge_symbol(symbol, market)
    keys = _symbol_match_keys(symbol) | _symbol_match_keys(lb) | _symbol_match_keys(f'{symbol}.{market}')
    if not keys:
        return None
    for pos in positions or []:
        pos_keys = _symbol_match_keys(str(pos.get('symbol') or ''))
        if keys & pos_keys:
            return pos
    return None


class AutoTradeService:
    """
    自选股 AI 自动交易与日内风控护栏服务。

    默认只扫描；显式 execute=True 且长桥凭据齐全时按当前用户凭据向券商提交委托。
    """

    DEFAULT_CONFIG = {
        'enabled': True,
        'auto_execute': False,
        'interval': 900,
        'strategy_profile': 'balanced',
        'max_symbols': 3,
        'max_amount_per_symbol': 0.0,
        'max_daily_orders': 10,
        'max_daily_notional_amount': 0.0,
        'max_position_ratio': DAILY_BUY_POSITION_RATIO,
        'max_symbol_position_pct': DEFAULT_MAX_SYMBOL_POSITION_PCT,
        'min_confidence': 65,
        'price_slippage_tolerance': 0.03,
        'scan_markets': tuple(sorted(AUTO_TRADE_MARKETS)),
        'max_gross_exposure_pct': MAX_GROSS_EXPOSURE_PCT,
        'skip_held_buy': True,
        'skip_cn': True,
    }

    @classmethod
    def _generate_cycle_id(cls) -> str:
        return f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    @classmethod
    async def _today_stats(cls, db: AsyncSession, user_id: int | None = None) -> tuple[int, float]:
        """日内已提交委托统计；user_id 非空时只统计该用户自己的决策（护栏按账户隔离）。"""
        today_start = datetime.combine(date.today(), datetime.min.time())
        stmt = select(
            func.count(PlatAutoTradeDecision.decision_id),
            func.sum(PlatAutoTradeDecision.quantity * PlatAutoTradeDecision.price),
        ).where(
            PlatAutoTradeDecision.create_time >= today_start,
            PlatAutoTradeDecision.status.in_(['submitted', 'filled']),
        )
        if user_id is not None:
            stmt = stmt.where(PlatAutoTradeDecision.user_id == int(user_id))
        res = await db.execute(stmt)
        row = res.first()
        return int(row[0] or 0) if row else 0, float(row[1] or 0.0) if row else 0.0

    @classmethod
    async def _today_bought_symbols(cls, db: AsyncSession, user_id: int | None) -> set[str]:
        """当日已提交/成交的买入标的（按账户隔离，阻止扫描循环重复加仓）。"""
        if user_id is None:
            return set()
        today_start = datetime.combine(date.today(), datetime.min.time())
        stmt = select(PlatAutoTradeDecision.symbol).where(
            PlatAutoTradeDecision.create_time >= today_start,
            PlatAutoTradeDecision.user_id == int(user_id),
            PlatAutoTradeDecision.side == 'BUY',
            PlatAutoTradeDecision.status.in_(list(TODAY_BUY_STATUSES)),
        )
        res = await db.execute(stmt)
        return {parse_symbol_market(s)[0] for s in res.scalars().all() if s}

    @classmethod
    def _serialize_log(cls, log: PlatAiTradeRunLog) -> dict[str, Any]:
        return {
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
            'message': log.message,
            'startedAt': log.started_at.strftime('%Y-%m-%d %H:%M:%S') if log.started_at else None,
            'finishedAt': log.finished_at.strftime('%Y-%m-%d %H:%M:%S') if log.finished_at else None,
        }

    @classmethod
    def _serialize_decision(cls, d: PlatAutoTradeDecision) -> dict[str, Any]:
        return {
            'decisionId': d.decision_id,
            'cycleId': d.cycle_id,
            'userId': getattr(d, 'user_id', None),
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
    @classmethod
    def _append_target(
        cls, items: list[dict[str, str]], seen: set[tuple[str, str]], symbol: str, market: str
    ) -> None:
        sym = str(symbol or '').strip()
        mkt = str(market or 'US').strip().upper()
        if not sym:
            return
        if '.' in sym:
            sym, inferred = parse_symbol_market(sym, mkt)
            mkt = inferred or mkt
        if not is_auto_trade_market(mkt, sym):
            return
        key = (sym.upper(), mkt)
        if key in seen:
            return
        seen.add(key)
        items.append({'symbol': sym, 'market': mkt})

    @classmethod
    async def _heat_scan_universe(cls, db: AsyncSession) -> list[dict[str, str]]:
        """与行情热度相同的 Top50 池，仅美股/港股。"""
        from module_market.dao.heat_dao import MarketHeatDao

        items: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for market in ('US', 'HK'):
            heat = await MarketHeatDao.get_latest_heat(db, market)
            if not heat or not getattr(heat, 'trade_date', None):
                continue
            rows = await MarketHeatDao.list_top50(db, market, heat.trade_date)
            for row in rows:
                cls._append_target(items, seen, str(getattr(row, 'symbol', '') or ''), market)
        return items

    @classmethod
    async def _resolve_targets(
        cls, db: AsyncSession, symbols: list[str] | list[dict[str, str]] | None, user_id: int | None = None
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        if symbols:
            for item in symbols:
                if isinstance(item, dict):
                    cls._append_target(
                        items,
                        seen,
                        str(item.get('symbol') or ''),
                        str(item.get('market') or 'US'),
                    )
                else:
                    sym, mkt = parse_symbol_market(str(item))
                    cls._append_target(items, seen, sym, mkt)
            return items

        heat_items = await cls._heat_scan_universe(db)
        for row in heat_items:
            cls._append_target(items, seen, row['symbol'], row['market'])

        from module_quant.dao.quant_dao import QuantWatchlistDao

        rows = await QuantWatchlistDao.get_enabled_symbols(db, user_id=user_id)
        for row in rows:
            cls._append_target(
                items,
                seen,
                str(getattr(row, 'symbol', '') or ''),
                str(getattr(row, 'market', '') or 'US'),
            )
        if items:
            return items
        from module_market.constant.instruments import TARGET_INSTRUMENTS

        for symbol, _name, mkt, category in TARGET_INSTRUMENTS:
            if category == 'index':
                continue
            cls._append_target(items, seen, symbol, mkt)
        return items

    @classmethod
    async def load_user_trade_settings(cls, db: AsyncSession, user_id: int | None) -> dict[str, Any]:
        from module_quant.dao.quant_dao import QuantLongbridgeConfigDao
        from module_quant.service.longbridge_service import resolve_longbridge_user_id

        target_id = resolve_longbridge_user_id(user_id)
        row = await QuantLongbridgeConfigDao.get_config(db, target_id)
        has_keys = bool(row and str(getattr(row, 'app_key', '') or '') and str(getattr(row, 'access_token', '') or ''))
        enabled = bool(has_keys and str(getattr(row, 'auto_trade_enabled', '0') or '0') == '1')
        try:
            ratio = float(getattr(row, 'daily_buy_ratio', None) or DAILY_BUY_POSITION_RATIO) if row else DAILY_BUY_POSITION_RATIO
        except (TypeError, ValueError):
            ratio = DAILY_BUY_POSITION_RATIO
        ratio = max(0.05, min(0.50, ratio))
        try:
            symbol_pct = float(
                getattr(row, 'max_symbol_position_pct', None) or DEFAULT_MAX_SYMBOL_POSITION_PCT
            ) if row else DEFAULT_MAX_SYMBOL_POSITION_PCT
        except (TypeError, ValueError):
            symbol_pct = DEFAULT_MAX_SYMBOL_POSITION_PCT
        symbol_pct = clamp_max_symbol_position_pct(symbol_pct)
        return {
            'user_id': target_id,
            'auto_trade_enabled': enabled,
            'daily_buy_ratio': ratio,
            'max_symbol_position_pct': symbol_pct,
            'has_keys': has_keys,
        }

    @classmethod
    async def save_user_trade_settings(
        cls,
        db: AsyncSession,
        user_id: int,
        *,
        auto_trade_enabled: bool,
        daily_buy_ratio: float | None = None,
        max_symbol_position_pct: float | None = None,
    ) -> dict[str, Any]:
        from exceptions.exception import ServiceException
        from module_quant.dao.quant_dao import QuantLongbridgeConfigDao

        existing = await QuantLongbridgeConfigDao.get_config(db, user_id)
        has_keys = bool(existing and (existing.app_key or '') and (existing.access_token or ''))
        if auto_trade_enabled and not has_keys:
            raise ServiceException(message='未配置长桥账户 Key，无法打开自动交易')
        ratio = daily_buy_ratio if daily_buy_ratio is not None else (
            float(getattr(existing, 'daily_buy_ratio', None) or DAILY_BUY_POSITION_RATIO) if existing else DAILY_BUY_POSITION_RATIO
        )
        if max_symbol_position_pct is not None:
            symbol_pct = max_symbol_position_pct
        else:
            try:
                symbol_pct = float(
                    getattr(existing, 'max_symbol_position_pct', None) or DEFAULT_MAX_SYMBOL_POSITION_PCT
                ) if existing else DEFAULT_MAX_SYMBOL_POSITION_PCT
            except (TypeError, ValueError):
                symbol_pct = DEFAULT_MAX_SYMBOL_POSITION_PCT
        symbol_pct = clamp_max_symbol_position_pct(symbol_pct)
        await QuantLongbridgeConfigDao.save_trade_settings(
            db,
            user_id,
            auto_trade_enabled=auto_trade_enabled,
            daily_buy_ratio=ratio,
            max_symbol_position_pct=symbol_pct,
        )
        await db.commit()
        return await cls.load_user_trade_settings(db, user_id)

    @classmethod
    async def get_status(cls, db: AsyncSession, user_id: int | None = None) -> dict[str, Any]:
        settings = await cls.load_user_trade_settings(db, user_id)
        await LongbridgeService.ensure_credentials_from_db(db, settings['user_id'])
        configured = LongbridgeService.is_configured()
        today_orders_count, today_notional_amount = await cls._today_stats(db, settings['user_id'])
        recent_logs = await TradeDao.list_ai_trade_run_logs(db, limit=5, user_id=settings['user_id'])
        recent_decisions = await TradeDao.list_auto_trade_decisions(db, limit=10)
        submit_allowed, submit_block_reason = resolve_submit_permission(
            execute=True,
            configured=configured,
            auto_trade_enabled=settings['auto_trade_enabled'],
        )
        net_assets = 0.0
        if configured:
            try:
                net_assets = pick_net_assets(await LongbridgeService.get_account_balance_async())
            except Exception as exc:
                logger.warning(f'[自动交易] 读取账户净资产失败: {exc}')
        max_daily = daily_buy_cap(net_assets, settings['daily_buy_ratio'])
        max_symbol_pct = clamp_max_symbol_position_pct(settings.get('max_symbol_position_pct'))
        max_per_symbol = symbol_position_cap(net_assets, max_symbol_pct)
        if not configured:
            status_message = '长桥凭据未配置，自动交易仅扫描、不会下单'
        elif not settings['auto_trade_enabled']:
            status_message = '本账户自动交易已关闭，只扫描不下单。打开开关后会按该账户配置的长桥凭据委托。'
        else:
            status_message = (
                f'本账户自动交易已开启。定时扫描与「扫描并尝试下单」会向该账户长桥凭据委托；'
                f'日内买入上限为仓位的 {int(settings["daily_buy_ratio"] * 100)}%，'
                f'单标的上限 {int(max_symbol_pct * 100)}%。'
            )
        return {
            'configured': configured,
            'autoTradeEnabled': settings['auto_trade_enabled'],
            'userId': settings['user_id'],
            'message': status_message,
            'tradingEnabled': settings['auto_trade_enabled'],
            'submitAllowed': submit_allowed,
            'submitBlockReason': None if submit_allowed else submit_block_reason,
            'config': {
                **cls.DEFAULT_CONFIG,
                'auto_execute': settings['auto_trade_enabled'],
                'max_daily_notional_amount': max_daily,
                'max_amount_per_symbol': max_per_symbol,
                'max_position_ratio': settings['daily_buy_ratio'],
                'max_symbol_position_pct': max_symbol_pct,
            },
            'guardrails': {
                'todayOrdersCount': today_orders_count,
                'maxDailyOrders': cls.DEFAULT_CONFIG['max_daily_orders'],
                'todayNotionalAmount': round(today_notional_amount, 2),
                'maxDailyNotionalAmount': max_daily,
                'maxAmountPerSymbol': max_per_symbol,
                'maxSymbolPositionPct': max_symbol_pct,
                'netAssets': round(net_assets, 2),
                'dailyBuyRatio': settings['daily_buy_ratio'],
                'tradingEnabled': settings['auto_trade_enabled'],
                'autoTradeEnabled': settings['auto_trade_enabled'],
                'isOrderLimitReached': today_orders_count >= cls.DEFAULT_CONFIG['max_daily_orders'],
                'isAmountLimitReached': max_daily > 0 and today_notional_amount >= max_daily,
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
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """
        跑一次自动交易扫描。

        默认标的池：美/港行情热度 Top50（可叠加该用户美/港自选）；A 股不扫不下单。
        多账户语义：user_id 决定用谁的券商凭据和护栏额度。
        不传 user_id 时回退请求上下文用户，再回退管理员(1)。
        """
        from module_quant.service.longbridge_service import (
            resolve_longbridge_user_id,
        )

        target_user_id = resolve_longbridge_user_id(user_id)
        settings = await cls.load_user_trade_settings(db, target_user_id)
        cycle_id = cls._generate_cycle_id()
        started_at = datetime.now()
        config = merge_runtime_config(custom_config)
        if strategy_profile:
            config['strategy_profile'] = strategy_profile

        await LongbridgeService.ensure_credentials_from_db(db, target_user_id)
        target_items = await cls._resolve_targets(db, symbols, user_id=target_user_id)

        logger.info(
            f'[AI自动交易] 启动扫描 cycle_id={cycle_id}, 标的数={len(target_items)}, source={source}, execute={execute}'
        )

        if not target_items:
            summary_msg = (
                f'用户 {target_user_id} 扫描池为空（美/港热度 Top50 且无可用自选）。'
                'A 股不参与自动交易。请等待热度任务写入或添加美/港自选。'
            )
            finished_at = datetime.now()
            await TradeDao.add_ai_trade_run_log(
                db,
                {
                    'cycle_id': cycle_id,
                    'user_id': target_user_id,
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

        from module_quant.service.quant_service import QuantService

        profile_code = str(config.get('strategy_profile') or 'balanced')
        profile_cfg = await QuantService.load_profile_config(db, profile_code, user_id=target_user_id)
        scan_cfg = dict(profile_cfg or {})
        if isinstance(config.get('custom_thresholds'), dict):
            scan_cfg.update(config['custom_thresholds'])
        scan_res = await StrategyService.run_strategy_cycle_async(
            symbols=target_items,
            profile=profile_code,
            custom_config=scan_cfg or None,
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
            if is_opp and not is_auto_trade_market(item.get('market'), item.get('symbol')):
                is_opp = False
            candidate_record = slim_scan_row(
                {
                    'symbol': item.get('symbol'),
                    'market': item.get('market', 'US'),
                    'price': price,
                    'signal': decision,
                    'confidence': confidence,
                    'reason': item.get('reason'),
                    'isOpportunity': is_opp,
                    'score': {'total': score_val},
                }
            )
            candidates.append(candidate_record)
            if is_opp:
                opportunities.append(candidate_record)

        try:
            from module_quant.dao.quant_dao import QuantSnapshotDao

            for item in scan_results:
                metrics = ((item.get('factor_json') or {}).get('metrics') or {})
                if not item.get('symbol') or not isinstance(metrics, dict):
                    continue
                await QuantSnapshotDao.replace_alpha_values(
                    db,
                    symbol=str(item.get('symbol')),
                    market=str(item.get('market') or 'US'),
                    as_of=str(metrics.get('tradeDate') or '')[:16],
                    alpha101=metrics.get('alpha101') or {},
                    alpha158=metrics.get('alpha158') or {},
                )
        except Exception:
            logger.exception(f'[AI自动交易] 写入 Alpha 因子表失败 cycle_id={cycle_id}')

        opportunities.sort(
            key=lambda x: (x.get('confidence', 0), float((x.get('score') or {}).get('total', 0))),
            reverse=True,
        )

        should_execute = bool(execute) if execute is not None else bool(settings['auto_trade_enabled'])
        configured = LongbridgeService.is_configured()
        can_submit, submit_block = resolve_submit_permission(
            execute=should_execute,
            configured=configured,
            auto_trade_enabled=settings['auto_trade_enabled'],
        )

        submitted_decisions: list[dict[str, Any]] = []
        submitted_count = 0
        positions: list[dict[str, Any]] = []
        net_assets = 0.0
        available_cash = 0.0
        account_snapshot: dict[str, Any] | None = None
        if configured:
            try:
                account_snapshot = await LongbridgeService.get_account_balance_async()
                net_assets = pick_net_assets(account_snapshot)
                available_cash = pick_available_cash(account_snapshot)
            except Exception as exc:
                logger.warning(f'[AI自动交易] 读取账户净资产失败: {exc}')
        buy_ratio = float(settings['daily_buy_ratio'])
        max_symbol_pct = clamp_max_symbol_position_pct(settings.get('max_symbol_position_pct'))
        max_daily = daily_buy_cap(net_assets, buy_ratio)
        max_per_symbol = symbol_position_cap(net_assets, max_symbol_pct)
        config['max_daily_notional_amount'] = max_daily
        config['max_amount_per_symbol'] = max_per_symbol
        config['max_position_ratio'] = buy_ratio
        config['max_symbol_position_pct'] = max_symbol_pct

        today_orders_count, today_notional_amount = await cls._today_stats(db, target_user_id)
        guardrail_snapshot = {
            'todayOrdersCount': today_orders_count,
            'maxDailyOrders': config['max_daily_orders'],
            'todayNotionalAmount': round(today_notional_amount, 2),
            'maxDailyNotionalAmount': max_daily,
            'maxSymbols': config['max_symbols'],
            'maxAmountPerSymbol': max_per_symbol,
            'maxSymbolPositionPct': max_symbol_pct,
            'netAssets': round(net_assets, 2),
            'dailyBuyRatio': buy_ratio,
            'maxGrossExposurePct': MAX_GROSS_EXPOSURE_PCT,
            'availableCash': round(available_cash, 2),
            'autoTradeEnabled': settings['auto_trade_enabled'],
            'configured': configured,
            'submitAllowed': can_submit,
            'submitBlockReason': submit_block,
            'priceSlippageTolerance': config['price_slippage_tolerance'],
            'totalPositionMv': 0.0,
            'grossRoom': remaining_gross_room(net_assets, 0.0),
        }

        if can_submit and opportunities:
            try:
                pos_res = await LongbridgeService.get_positions_async()
                positions = pos_res.get('positions') or []
                if pos_res.get('configured') is False:
                    skipped_reasons.append(
                        {'symbol': '*', 'reason': pos_res.get('message') or '长桥凭据未配置，已跳过委托'}
                    )
                    can_submit = False
            except Exception as exc:
                logger.exception(f'[AI自动交易] 读取券商账户失败 cycle_id={cycle_id}')
                skipped_reasons.append({'symbol': '*', 'reason': f'读取券商账户失败: {exc}'})
                can_submit = False
            if net_assets <= 0:
                skipped_reasons.append(
                    {'symbol': '*', 'reason': f'账户净资产为 0，无法按仓位 {int(buy_ratio * 100)}% 计算日内买入额度'}
                )
                can_submit = False

        total_mv = total_position_market_value(positions)
        gross_room = remaining_gross_room(net_assets, total_mv)
        guardrail_snapshot['totalPositionMv'] = round(total_mv, 2)
        guardrail_snapshot['grossRoom'] = round(gross_room, 2)
        guardrail_snapshot['availableCash'] = round(available_cash, 2)
        if can_submit and opportunities and gross_room < MIN_TARGET_AMOUNT_USD:
            skipped_reasons.append(
                {
                    'symbol': '*',
                    'reason': (
                        f'总持仓 ${total_mv:.0f} 已达或超过净资产 ${net_assets:.0f}，停止买入'
                    ),
                }
            )
            can_submit = False
        if can_submit and opportunities and available_cash < MIN_TARGET_AMOUNT_USD:
            skipped_reasons.append(
                {'symbol': '*', 'reason': f'可用现金不足 (${available_cash:.2f})，停止买入'}
            )
            can_submit = False

        today_bought: set[str] = set()
        if can_submit and opportunities:
            today_bought = await cls._today_bought_symbols(db, target_user_id)
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

                try:
                    quote = await LongbridgeService.get_realtime_quote_async(symbol, market)
                    realtime_price = LongbridgeService.extract_last_price(quote, symbol)
                except Exception as exc:
                    logger.warning(f'[AI自动交易] 获取 {symbol} 实时报价失败: {exc}')
                    skipped_reasons.append({'symbol': symbol, 'reason': f'获取实时报价失败: {exc}'})
                    continue
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
                    if not is_auto_trade_market(market, symbol):
                        skipped_reasons.append({'symbol': symbol, 'reason': 'A股不参与自动交易'})
                        continue
                    if should_skip_duplicate_buy(symbol, today_bought):
                        skipped_reasons.append({'symbol': symbol, 'reason': '今日已买入该标的，跳过重复加仓'})
                        continue
                    pos = match_position(positions, symbol, market)
                    if should_skip_held_buy(pos):
                        skipped_reasons.append({'symbol': symbol, 'reason': '已持有该标的，跳过重复买入'})
                        continue
                    existing_mv = existing_position_market_value(pos, realtime_price)
                    room = symbol_buy_room(net_assets, max_symbol_pct, existing_mv)
                    if room < MIN_TARGET_AMOUNT_USD:
                        skipped_reasons.append(
                            {
                                'symbol': symbol,
                                'reason': f'已达单标的仓位上限 ({int(max_symbol_pct * 100)}% NAV)',
                            }
                        )
                        continue
                    remaining_daily = max(0.0, max_daily - today_notional_amount)
                    gross_room = remaining_gross_room(net_assets, total_mv)
                    target_amount = min(remaining_daily, room, gross_room, max(0.0, available_cash))
                    if target_amount < MIN_TARGET_AMOUNT_USD:
                        skipped_reasons.append(
                            {
                                'symbol': symbol,
                                'reason': (
                                    f'剩余额度不足 (${target_amount:.2f})：日内/单票/总仓位/现金'
                                ),
                            }
                        )
                        continue
                    quantity = max(1, int(target_amount / realtime_price))

                order_price = round_limit_price(realtime_price, market)
                if order_price <= 0:
                    skipped_reasons.append({'symbol': symbol, 'reason': '委托价无效，跳过下单'})
                    continue
                order_amount = quantity * order_price
                try:
                    order_res = await LongbridgeService.submit_order_async(
                        symbol=symbol,
                        side=side,
                        order_type='LO',
                        quantity=quantity,
                        price=order_price,
                        market=market,
                    )
                except Exception as exc:
                    logger.warning(f'[AI自动交易] {symbol} 下单异常: {exc}')
                    order_res = {'ok': False, 'message': f'下单异常: {exc}'}
                ok = bool(order_res.get('ok'))
                status = 'submitted' if ok else 'rejected'
                order_id = LongbridgeService.extract_order_id(order_res)
                error_msg = None if ok else (order_res.get('message') or '下单失败')

                decision_dict = {
                    'cycle_id': cycle_id,
                    'user_id': target_user_id,
                    'symbol': symbol,
                    'market': market,
                    'side': side,
                    'quantity': quantity,
                    'price': order_price,
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
                    if side == 'BUY':
                        code, _ = parse_symbol_market(symbol, market)
                        if code:
                            today_bought.add(code)
                        total_mv += order_amount
                        available_cash = max(0.0, available_cash - order_amount)
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

        log_payload = {
            'cycle_id': cycle_id,
            'user_id': target_user_id,
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
        }
        try:
            await TradeDao.add_ai_trade_run_log(db, log_payload)
            await db.commit()
        except Exception:
            logger.exception(f'[AI自动交易] 写入完整台账失败，降级为摘要 cycle_id={cycle_id}')
            await db.rollback()
            log_payload['candidates_snapshot'] = json.dumps(
                [{'symbol': c.get('symbol'), 'signal': c.get('signal'), 'confidence': c.get('confidence')} for c in opportunities],
                ensure_ascii=False,
            )
            log_payload['opportunities_snapshot'] = json.dumps(opportunities, ensure_ascii=False, default=str)
            await TradeDao.add_ai_trade_run_log(db, log_payload)
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
