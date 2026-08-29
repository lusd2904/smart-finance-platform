"""手工下单与紧急停机护栏。

自动交易的仓位/日内名义本金/总敞口复用同一套计算；停机开关拦住手工、自动、次日清单。
自动交易开关本身不挡手工单。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from module_trade.service.auto_trade_service import (
    clamp_max_symbol_position_pct,
    daily_buy_cap,
    existing_position_market_value,
    match_position,
    parse_symbol_market,
    pick_available_cash,
    pick_net_assets,
    position_quantity,
    remaining_gross_room,
    symbol_buy_room,
)
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

HALT_REDIS_KEY = 'sfp:trade:halt'
BUY_SIDES = frozenset({'buy', 'b', '买', '买入'})
SELL_SIDES = frozenset({'sell', 's', '卖', '卖出'})
SKIP_ORDER_STATUS = frozenset({'cancelled', 'canceled', 'rejected', 'expired', 'failed'})
_memory_halt: dict[str, Any] = {'halted': False, 'reason': '', 'by': None, 'at': ''}


def normalize_side(side: str | None) -> str:
    text = str(side or '').strip().lower()
    if text in BUY_SIDES:
        return 'buy'
    if text in SELL_SIDES:
        return 'sell'
    return text


def is_buy_side(side: str | None) -> bool:
    return normalize_side(side) == 'buy'


def order_notional(quantity: float, price: float | None) -> float:
    try:
        qty = float(quantity or 0)
        px = float(price or 0)
    except (TypeError, ValueError):
        return 0.0
    if qty <= 0 or px <= 0:
        return 0.0
    return round(qty * px, 2)


def today_buy_notional_from_orders(orders: list[dict[str, Any]] | None) -> tuple[int, float]:
    """统计今日仍有效的买入名义本金（跳过已撤/拒绝）。"""
    count = 0
    notional = 0.0
    for row in orders or []:
        status = str(row.get('status') or '').lower().replace(' ', '_')
        if status in SKIP_ORDER_STATUS:
            continue
        count += 1
        if not is_buy_side(str(row.get('side') or '')):
            continue
        qty = float(row.get('quantity') or row.get('executedQuantity') or 0)
        price = float(row.get('price') or row.get('executedPrice') or 0)
        if qty > 0 and price > 0:
            notional += qty * price
    return count, round(notional, 2)


def buy_blocked_reason(
    *,
    notional: float,
    net_assets: float,
    available_cash: float,
    total_mv: float,
    existing_mv: float,
    today_notional: float,
    daily_buy_ratio: float,
    max_symbol_pct: float,
) -> str | None:
    """纯计算：手工买入是否越过账户护栏。"""
    if notional <= 0:
        return '无法估算买入金额（需要有效价格与数量）'
    if net_assets <= 0:
        return '账户净资产为 0，无法计算仓位上限'
    max_daily = daily_buy_cap(net_assets, daily_buy_ratio)
    remaining_daily = max(0.0, max_daily - max(0.0, today_notional))
    if notional > remaining_daily + 1e-6:
        return (
            f'超过日内买入上限：本单 ${notional:.2f}，剩余 ${remaining_daily:.2f}'
            f'（净资产 {int(daily_buy_ratio * 100)}% = ${max_daily:.2f}）'
        )
    room = symbol_buy_room(net_assets, max_symbol_pct, existing_mv)
    if notional > room + 1e-6:
        return f'超过单标的仓位上限（净资产 {int(clamp_max_symbol_position_pct(max_symbol_pct) * 100)}%）'
    gross = remaining_gross_room(net_assets, total_mv)
    if notional > gross + 1e-6:
        return f'总持仓已接近或超过净资产（持仓 ${total_mv:.0f} / 净资产 ${net_assets:.0f}），停止买入'
    if notional > available_cash + 1e-6:
        return f'可用现金不足（需要 ${notional:.2f}，可用 ${available_cash:.2f}）'
    return None


def sell_blocked_reason(*, quantity: float, available_qty: float) -> str | None:
    if quantity <= 0:
        return '卖出数量必须大于 0'
    if available_qty <= 0:
        return '无可用持仓，无法卖出'
    if quantity > available_qty + 1e-6:
        return f'卖出数量 {quantity:g} 超过可用持仓 {available_qty:g}'
    return None


def _halt_payload() -> dict[str, Any]:
    return {
        'halted': bool(_memory_halt.get('halted')),
        'reason': str(_memory_halt.get('reason') or ''),
        'by': _memory_halt.get('by'),
        'at': str(_memory_halt.get('at') or ''),
    }


async def read_halt() -> dict[str, Any]:
    """Redis 优先；测试/Redis 未就绪时用进程内状态。读失败视为未停机。"""
    try:
        from config.get_redis import RedisUtil

        redis = RedisUtil.get_client()
        if redis is None:
            return _halt_payload()
        raw = await redis.get(HALT_REDIS_KEY)
        if not raw:
            return {'halted': False, 'reason': '', 'by': None, 'at': ''}
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            return {
                'halted': bool(data.get('halted')),
                'reason': str(data.get('reason') or ''),
                'by': data.get('by'),
                'at': str(data.get('at') or ''),
            }
    except Exception as exc:
        logger.warning(f'[下单护栏] 读取停机开关失败: {exc}')
    return _halt_payload()


async def write_halt(*, halted: bool, reason: str = '', user_id: int | None = None) -> dict[str, Any]:
    from utils.time_format_util import now_beijing

    payload = {
        'halted': bool(halted),
        'reason': str(reason or ('紧急停机' if halted else '')),
        'by': user_id,
        'at': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _memory_halt.clear()
    _memory_halt.update(payload)
    try:
        from config.get_redis import RedisUtil

        redis = RedisUtil.get_client()
        if redis is not None:
            await redis.set(HALT_REDIS_KEY, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning(f'[下单护栏] 写入停机开关失败: {exc}')
    return dict(payload)


async def halt_block_reason() -> str | None:
    snap = await read_halt()
    if snap.get('halted'):
        extra = str(snap.get('reason') or '').strip()
        return f'紧急停机中，禁止新委托{("：" + extra) if extra else ""}'
    return None


def _reject(message: str) -> dict[str, Any]:
    return {'ok': False, 'blocked': True, 'message': message, 'reason': message}


async def _positions() -> list[dict[str, Any]]:
    from module_quant.service.longbridge_service import LongbridgeService

    try:
        return list((await LongbridgeService.get_positions_async()).get('positions') or [])
    except Exception as exc:
        logger.warning(f'[下单护栏] 读取持仓失败: {exc}')
        return []


async def _last_price(code: str, market: str, fallback: float) -> float:
    if fallback > 0:
        return fallback
    from module_quant.service.longbridge_service import LongbridgeService

    try:
        quote = await LongbridgeService.get_realtime_quote_async(code, market)
        return float(LongbridgeService.extract_last_price(quote, code) or 0)
    except Exception as exc:
        logger.warning(f'[下单护栏] 读取报价失败 {code}: {exc}')
        return 0.0


async def _account_snapshot() -> tuple[float, float]:
    from module_quant.service.longbridge_service import LongbridgeService

    try:
        account = await LongbridgeService.get_account_balance_async()
        return pick_net_assets(account), pick_available_cash(account)
    except Exception as exc:
        logger.warning(f'[下单护栏] 读取账户失败: {exc}')
        return 0.0, 0.0


async def _today_buy_notional(query_db: AsyncSession, user_id: int) -> float:
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.auto_trade_service import AutoTradeService

    try:
        today = await LongbridgeService.get_today_orders_async()
        _count, notional = today_buy_notional_from_orders(today.get('orders') or [])
        return notional
    except Exception as exc:
        logger.warning(f'[下单护栏] 读取今日委托失败: {exc}')
        try:
            _count, notional = await AutoTradeService._today_stats(query_db, user_id)
            return notional
        except Exception:
            return 0.0


async def evaluate_manual_order(
    query_db: AsyncSession,
    *,
    user_id: int | None,
    symbol: str,
    side: str,
    quantity: float,
    price: float | None,
    market: str = 'US',
) -> dict[str, Any]:
    """手工单前置检查。通过时 ok=True；拒绝时不打长桥。"""
    halt = await halt_block_reason()
    if halt:
        return _reject(halt)

    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.service.auto_trade_service import AutoTradeService

    settings = await AutoTradeService.load_user_trade_settings(query_db, user_id)
    await LongbridgeService.ensure_credentials_from_db(query_db, settings['user_id'])
    if not LongbridgeService.is_configured():
        return _reject('长桥凭据未配置')

    code, mkt = parse_symbol_market(symbol if '.' in str(symbol) else f'{symbol}.{market}')
    if not code:
        code, mkt = str(symbol or '').strip().upper(), str(market or 'US').upper()
    if str(market or '').strip():
        mkt = str(market).strip().upper()
    positions = await _positions()

    if normalize_side(side) == 'sell':
        reason = sell_blocked_reason(
            quantity=float(quantity or 0),
            available_qty=position_quantity(match_position(positions, code, mkt)),
        )
        return _reject(reason) if reason else {'ok': True, 'blocked': False, 'message': ''}

    px = await _last_price(code, mkt, float(price or 0))
    net_assets, available_cash = await _account_snapshot()
    pos = match_position(positions, code, mkt)
    reason = buy_blocked_reason(
        notional=order_notional(quantity, px),
        net_assets=net_assets,
        available_cash=available_cash,
        total_mv=round(sum(existing_position_market_value(item) for item in positions), 2),
        existing_mv=existing_position_market_value(pos, px),
        today_notional=await _today_buy_notional(query_db, settings['user_id']),
        daily_buy_ratio=float(settings['daily_buy_ratio']),
        max_symbol_pct=float(settings['max_symbol_position_pct']),
    )
    if reason:
        return _reject(reason)
    return {'ok': True, 'blocked': False, 'message': '', 'notional': order_notional(quantity, px)}
