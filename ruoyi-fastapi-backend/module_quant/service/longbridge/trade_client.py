"""长桥交易客户端：TradeContext 与账户资金、持仓、订单、下单/撤单。"""

from __future__ import annotations

import asyncio
from typing import Any

from module_quant.service.longbridge.auth import ACCOUNT_CACHE_TTL
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.longbridge_breaker import LongbridgeBreaker


class TradeClientMixin:
    """交易相关方法，由 LongbridgeService 组合继承。"""

    _cached_trade_ctxs: dict[str, Any] = {}

    @classmethod
    def _build_trade_context(cls) -> Any:
        """构建/复用 TradeContext（延迟导入）。熔断开闸时不再建连。"""
        if cls._blocked():
            return None
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        cached = cls._cached_trade_ctxs.get(sig)
        if cached is not None:
            return cached

        config = cls._build_config()
        if config is None:
            return None
        from longport.openapi import TradeContext  # 延迟导入，SDK 为可选依赖

        try:
            ctx = TradeContext(config)
            cls._cached_trade_ctxs[sig] = ctx
            return ctx
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 构建TradeContext失败: {exc}')
            return None

    @classmethod
    def get_account_balance(cls) -> dict[str, Any]:
        """获取账户资金。凭据为空返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'balances': []}
        if cls._blocked():
            return {'configured': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'balances': []}
        try:
            ctx = cls._build_trade_context()
            if ctx is None:
                return {'configured': True, 'reason': 'unavailable', 'message': '长桥 TradeContext 不可用', 'balances': []}
            raw = ctx.account_balance()
            balances = [
                {
                    'currency': getattr(b, 'currency', None),
                    'totalCash': cls._to_float(getattr(b, 'total_cash', None)),
                    'availableCash': cls._to_float(getattr(b, 'available_cash', None)),
                    'netAssets': cls._to_float(getattr(b, 'net_assets', None)),
                    'maxFinanceAmount': cls._to_float(getattr(b, 'max_finance_amount', None)),
                }
                for b in raw or []
            ]
            LongbridgeBreaker.record_success()
            return {'configured': True, 'balances': balances}
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取账户资金失败: {exc}')
            return {'configured': True, 'message': f'获取账户资金失败: {exc}', 'balances': []}

    @classmethod
    def get_positions(cls) -> dict[str, Any]:
        """获取持仓。凭据为空返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'positions': []}
        if cls._blocked():
            return {'configured': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'positions': []}
        try:
            ctx = cls._build_trade_context()
            if ctx is None:
                return {'configured': True, 'reason': 'unavailable', 'message': '长桥 TradeContext 不可用', 'positions': []}
            raw = ctx.stock_positions()
            channels = getattr(raw, 'channels', None) or []
            positions = [
                {
                    'symbol': getattr(p, 'symbol', None),
                    'symbolName': getattr(p, 'symbol_name', None),
                    'quantity': cls._to_float(getattr(p, 'quantity', None)),
                    'availableQuantity': cls._to_float(getattr(p, 'available_quantity', None)),
                    'costPrice': cls._to_float(getattr(p, 'cost_price', None)),
                    'currency': getattr(p, 'currency', None),
                }
                for channel in channels
                for p in getattr(channel, 'positions', None) or []
            ]
            LongbridgeBreaker.record_success()
            return {'configured': True, 'positions': positions}
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取持仓失败: {exc}')
            return {'configured': True, 'message': f'获取持仓失败: {exc}', 'positions': []}

    @classmethod
    def get_today_orders(cls) -> dict[str, Any]:
        """今日订单。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'orders': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.today_orders()
            orders = [cls._map_order(o) for o in (raw or [])]
            return {'configured': True, 'orders': orders}
        except Exception as exc:
            logger.warning(f'[长桥] 获取今日订单失败: {exc}')
            return {'configured': True, 'message': f'获取今日订单失败: {exc}', 'orders': []}

    @classmethod
    def get_history_orders(cls, limit: int = 50) -> dict[str, Any]:
        """历史订单（SDK 支持范围内）。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'orders': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.history_orders()
            orders = [cls._map_order(o) for o in (raw or [])][: max(1, min(limit, 200))]
            return {'configured': True, 'orders': orders}
        except Exception as exc:
            logger.warning(f'[长桥] 获取历史订单失败: {exc}')
            return {'configured': True, 'message': f'获取历史订单失败: {exc}', 'orders': []}

    @classmethod
    def submit_order(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'LO',
        price: float | None = None,
        time_in_force: str = 'Day',
        market: str = 'US',
        allow_sim: bool = False,
    ) -> dict[str, Any]:
        """
        提交订单。side: buy/sell；order_type: LO/MO 等。
        默认需开启实盘开关；allow_sim=True 时按当前用户凭据下单（产品约定配置的是模拟账户）。
        """
        if not cls.is_configured():
            return {'configured': False, 'ok': False, 'message': '长桥凭据未配置'}
        if not allow_sim and not cls.is_trading_enabled():
            return {
                'configured': True,
                'ok': False,
                'message': '实盘交易未启用，当前为只读/模拟模式，请管理员在系统设置中开启后再试',
            }
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            from longport.openapi import (  # 延迟导入，SDK 为可选依赖
                OrderSide,
                OrderType,
                TimeInForceType,
            )

            side_enum = OrderSide.Buy if str(side).lower() in {'buy', 'b', '买', '买入'} else OrderSide.Sell
            ot = str(order_type or 'LO').upper()
            type_map = {
                'LO': OrderType.LO,
                'MO': OrderType.MO,
                'ELO': getattr(OrderType, 'ELO', OrderType.LO),
                'AO': getattr(OrderType, 'AO', OrderType.LO),
            }
            type_enum = type_map.get(ot, OrderType.LO)
            tif = TimeInForceType.Day
            ctx = cls._build_trade_context()
            kwargs: dict[str, Any] = {
                'side': side_enum,
                'submitted_quantity': quantity,
                'time_in_force': tif,
                'symbol': lb_symbol,
                'order_type': type_enum,
            }
            if ot == 'LO' and price is not None:
                kwargs['submitted_price'] = price
            resp = ctx.submit_order(**kwargs)
            order_id = getattr(resp, 'order_id', None) or getattr(resp, 'orderId', None)
            return {'configured': True, 'ok': True, 'orderId': order_id, 'symbol': lb_symbol, 'message': '下单已提交'}
        except Exception as exc:
            logger.warning(f'[长桥] 下单失败: {exc}')
            return {'configured': True, 'ok': False, 'message': f'下单失败: {exc}'}

    @classmethod
    def cancel_order(cls, order_id: str) -> dict[str, Any]:
        """撤单。"""
        if not cls.is_configured():
            return {'configured': False, 'ok': False, 'message': '长桥凭据未配置'}
        if not cls.is_trading_enabled():
            return {
                'configured': True,
                'ok': False,
                'message': '实盘交易未启用，当前为只读/模拟模式，请管理员在系统设置中开启后再试',
            }
        try:
            ctx = cls._build_trade_context()
            ctx.cancel_order(order_id)
            return {'configured': True, 'ok': True, 'orderId': order_id, 'message': '撤单已提交'}
        except Exception as exc:
            logger.warning(f'[长桥] 撤单失败: {exc}')
            return {'configured': True, 'ok': False, 'message': f'撤单失败: {exc}'}

    @classmethod
    def _map_order(cls, o: Any) -> dict[str, Any]:
        status = str(getattr(o, 'status', '') or '')
        executed_qty = cls._to_float(getattr(o, 'executed_quantity', None))
        qty = cls._to_float(getattr(o, 'quantity', None) or getattr(o, 'submitted_quantity', None))
        return {
            'orderId': getattr(o, 'order_id', None) or getattr(o, 'orderId', None),
            'symbol': getattr(o, 'symbol', None),
            'stockName': getattr(o, 'stock_name', None) or getattr(o, 'symbol_name', None),
            'side': str(getattr(o, 'side', '') or ''),
            'status': status,
            'statusLabel': cls._order_status_label(status),
            'orderType': str(getattr(o, 'order_type', '') or ''),
            'quantity': qty,
            'price': cls._to_float(getattr(o, 'price', None) or getattr(o, 'submitted_price', None)),
            'executedQuantity': executed_qty,
            'executedPrice': cls._to_float(getattr(o, 'executed_price', None)),
            'currency': getattr(o, 'currency', None),
            'submittedAt': str(getattr(o, 'submitted_at', '') or ''),
            'updatedAt': str(getattr(o, 'updated_at', '') or getattr(o, 'last_done', '') or ''),
            'remark': str(getattr(o, 'msg', '') or getattr(o, 'remark', '') or ''),
            'filled': bool(executed_qty and qty and executed_qty >= qty),
            'open': status.lower() in {'submitted', 'new', 'wait_to_new', 'partial_filled', 'wait_to_cancel'},
        }

    @staticmethod
    def _order_status_label(status: str) -> str:
        text = str(status or '').lower().replace('_', '').replace(' ', '')
        checks = (
            ('partialfilled', '部分成交'),
            ('waittocancel', '待撤'),
            ('waittonew', '待报'),
            ('submitted', '已提交'),
            ('cancelled', '已撤'),
            ('canceled', '已撤'),
            ('rejected', '已拒绝'),
            ('expired', '已过期'),
            ('filled', '已成交'),
        )
        for key, label in checks:
            if key in text:
                return label
        if text in {'new', 'notreported'}:
            return '待成交'
        return status or '--'

    @classmethod
    def get_order(cls, order_id: str) -> dict[str, Any]:
        """在今日与历史委托中查找单笔订单。"""
        oid = str(order_id or '').strip()
        if not oid:
            return {'configured': cls.is_configured(), 'ok': False, 'message': '订单号为空', 'order': None}
        today = cls.get_today_orders()
        if not today.get('configured'):
            return {
                'configured': False,
                'ok': False,
                'message': today.get('message') or '长桥凭据未配置',
                'order': None,
            }
        for item in today.get('orders') or []:
            if str(item.get('orderId') or '') == oid:
                return {'configured': True, 'ok': True, 'order': item, 'scope': 'today'}
        history = cls.get_history_orders(100)
        for item in history.get('orders') or []:
            if str(item.get('orderId') or '') == oid:
                return {'configured': True, 'ok': True, 'order': item, 'scope': 'history'}
        return {'configured': True, 'ok': False, 'message': '未找到该订单', 'order': None}

    @classmethod
    def extract_order_id(cls, order_result: dict[str, Any]) -> str | None:
        if not order_result.get('ok'):
            return None
        data = order_result.get('data') if isinstance(order_result.get('data'), dict) else {}
        order_id = order_result.get('orderId') or (data or {}).get('order_id') or (data or {}).get('orderId')
        return str(order_id) if order_id else None

    @classmethod
    def flatten_account(cls, account_result: dict[str, Any]) -> dict[str, Any]:
        """把 {balances:[{totalCash, netAssets, ...}]} 压成前端常用扁平字段。"""
        balances = account_result.get('balances') or []
        first = balances[0] if balances else {}
        configured = bool(account_result.get('configured'))
        if not configured:
            return {
                'configured': False,
                'message': account_result.get('message') or '长桥凭据未配置',
                'currency': None,
                'totalCash': None,
                'availableCash': None,
                'netAssets': None,
                'balances': [],
            }
        return {
            'configured': True,
            'message': account_result.get('message'),
            'currency': first.get('currency') or 'USD',
            'totalCash': float(first.get('totalCash') or 0),
            'availableCash': float(first.get('availableCash') or first.get('totalCash') or 0),
            'netAssets': float(first.get('netAssets') or first.get('totalCash') or 0),
            'balances': balances,
        }

    # ------------------------------------------------------------- 异步封装 ---

    @classmethod
    async def get_account_balance_async(cls) -> dict[str, Any]:
        cache_key = f'lb:account:{cls._creds_cache_tag()}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        if cls._blocked():
            return {'configured': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'balances': []}
        await cls._throttle()
        data = await asyncio.to_thread(cls.get_account_balance)
        if data.get('configured') and data.get('balances'):
            await cache_set_json(cache_key, data, ACCOUNT_CACHE_TTL)
        return data

    @classmethod
    async def get_positions_async(cls) -> dict[str, Any]:
        cache_key = f'lb:positions:{cls._creds_cache_tag()}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        if cls._blocked():
            return {'configured': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'positions': []}
        await cls._throttle()
        data = await asyncio.to_thread(cls.get_positions)
        if data.get('configured'):
            await cache_set_json(cache_key, data, ACCOUNT_CACHE_TTL)
        return data

    @classmethod
    async def get_today_orders_async(cls) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_today_orders)

    @classmethod
    async def get_order_async(cls, order_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_order, order_id)

    @classmethod
    async def get_history_orders_async(cls, limit: int = 50) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_history_orders, limit)

    @classmethod
    async def submit_order_async(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'LO',
        price: float | None = None,
        time_in_force: str = 'Day',
        market: str = 'US',
        allow_sim: bool = False,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            cls.submit_order,
            symbol,
            side,
            quantity,
            order_type,
            price,
            time_in_force,
            market,
            allow_sim,
        )

    @classmethod
    async def cancel_order_async(cls, order_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(cls.cancel_order, order_id)
