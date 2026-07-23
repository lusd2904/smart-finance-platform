"""交易服务：封装长桥资金/持仓/订单，并提供简易通知/回测占位数据。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_quant.service.longbridge_service import LongbridgeService
from utils.log_util import logger

# 进程内简易通知（重启清空；后续可迁 DB）
_NOTIFICATIONS: list[dict[str, Any]] = []
_BACKTEST_RUNS: list[dict[str, Any]] = []
_AI_TRADE_RUNS: list[dict[str, Any]] = []


class TradeService:
    @classmethod
    async def _ensure(cls, query_db: AsyncSession) -> None:
        await LongbridgeService.ensure_credentials_from_db(query_db)

    @classmethod
    async def get_account_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, LongbridgeService.get_account_balance)

    @classmethod
    async def get_positions_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, LongbridgeService.get_positions)

    @classmethod
    async def get_orders_services(cls, query_db: AsyncSession, scope: str = 'today') -> dict[str, Any]:
        await cls._ensure(query_db)
        loop = asyncio.get_event_loop()
        if scope == 'history':
            return await loop.run_in_executor(None, LongbridgeService.get_history_orders, 100)
        return await loop.run_in_executor(None, LongbridgeService.get_today_orders)

    @classmethod
    async def submit_order_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'LO',
        price: float | None = None,
        market: str = 'US',
    ) -> dict[str, Any]:
        await cls._ensure(query_db)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: LongbridgeService.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
                market=market,
            ),
        )
        cls.push_notification(
            title=f'下单{"成功" if result.get("ok") else "失败"}',
            content=f'{side} {symbol} x {quantity} · {result.get("message")}',
            level='success' if result.get('ok') else 'danger',
            category='trade',
        )
        return result

    @classmethod
    async def cancel_order_services(cls, query_db: AsyncSession, order_id: str) -> dict[str, Any]:
        await cls._ensure(query_db)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, LongbridgeService.cancel_order, order_id)
        cls.push_notification(
            title=f'撤单{"成功" if result.get("ok") else "失败"}',
            content=f'订单 {order_id} · {result.get("message")}',
            level='warning' if result.get('ok') else 'danger',
            category='trade',
        )
        return result

    # ---------- 通知 ----------
    @classmethod
    def push_notification(
        cls, title: str, content: str, level: str = 'info', category: str = 'system'
    ) -> dict[str, Any]:
        item = {
            'id': int(datetime.now().timestamp() * 1000),
            'title': title,
            'content': content,
            'level': level,
            'category': category,
            'read': False,
            'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        _NOTIFICATIONS.insert(0, item)
        del _NOTIFICATIONS[200:]
        return item

    @classmethod
    def list_notifications(cls, limit: int = 50) -> list[dict[str, Any]]:
        return _NOTIFICATIONS[: max(1, min(limit, 200))]

    @classmethod
    def mark_notification_read(cls, notice_id: int | None = None) -> dict[str, Any]:
        if notice_id is None:
            for n in _NOTIFICATIONS:
                n['read'] = True
            return {'updated': len(_NOTIFICATIONS)}
        n = 0
        for item in _NOTIFICATIONS:
            if item['id'] == notice_id:
                item['read'] = True
                n += 1
        return {'updated': n}

    # ---------- 回测占位（基于历史K线简单动量） ----------
    @classmethod
    async def run_backtest_services(
        cls, query_db: AsyncSession, symbol: str, market: str = 'US', days: int = 120
    ) -> dict[str, Any]:
        from utils.influx_util import InfluxUtil

        loop = asyncio.get_event_loop()
        klines = await loop.run_in_executor(
            None, InfluxUtil.query_klines, market, symbol, f'-{max(days, 30)}d', 'now()'
        )
        if not klines or len(klines) < 30:
            return {
                'ok': False,
                'message': f'{symbol} K线不足，请先同步行情',
                'symbol': symbol,
            }
        closes = [float(k.get('close') or 0) for k in klines]
        # 简易均线交叉回测
        cash = 100000.0
        pos = 0.0
        equity = []
        trades = 0
        for i in range(20, len(closes)):
            ma5 = sum(closes[i - 5 : i]) / 5
            ma20 = sum(closes[i - 20 : i]) / 20
            price = closes[i]
            if ma5 > ma20 and pos == 0 and price > 0:
                pos = cash / price
                cash = 0
                trades += 1
            elif ma5 < ma20 and pos > 0:
                cash = pos * price
                pos = 0
                trades += 1
            equity.append({'date': klines[i].get('date'), 'equity': round(cash + pos * price, 2)})
        final = cash + pos * closes[-1]
        ret = round((final / 100000 - 1) * 100, 2)
        run = {
            'id': int(datetime.now().timestamp() * 1000),
            'symbol': symbol,
            'market': market,
            'days': days,
            'trades': trades,
            'returnPct': ret,
            'finalEquity': round(final, 2),
            'equity': equity[-60:],
            'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategy': 'MA5/MA20 cross',
            'ok': True,
            'message': '回测完成（简易动量策略）',
        }
        _BACKTEST_RUNS.insert(0, run)
        del _BACKTEST_RUNS[50:]
        cls.push_notification(
            title=f'回测完成 {symbol}',
            content=f'收益 {ret}% · 交易 {trades} 次',
            level='success',
            category='backtest',
        )
        return run

    @classmethod
    def list_backtests(cls) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in r.items() if k != 'equity'} | {'points': len(r.get('equity') or [])}
            for r in _BACKTEST_RUNS
        ]

    @classmethod
    def get_backtest(cls, run_id: int) -> dict[str, Any] | None:
        for r in _BACKTEST_RUNS:
            if r['id'] == run_id:
                return r
        return None

    # ---------- AI 自动交易台账（占位记录） ----------
    @classmethod
    def list_ai_trade_runs(cls) -> list[dict[str, Any]]:
        if not _AI_TRADE_RUNS:
            # 种子示例，便于页面不空
            now = datetime.now()
            for i, sym in enumerate(['AAPL', 'NVDA', 'MSFT']):
                _AI_TRADE_RUNS.append(
                    {
                        'id': i + 1,
                        'symbol': sym,
                        'signal': '观望' if i else '买入',
                        'status': 'completed',
                        'confidence': 60 + i * 8,
                        'note': '示例台账（接入调度后替换为真实运行）',
                        'createTime': (now - timedelta(hours=i * 3)).strftime('%Y-%m-%d %H:%M:%S'),
                    }
                )
        return list(_AI_TRADE_RUNS)

    @classmethod
    def add_ai_trade_run(cls, payload: dict[str, Any]) -> dict[str, Any]:
        item = {
            'id': int(datetime.now().timestamp() * 1000),
            'symbol': payload.get('symbol') or '',
            'signal': payload.get('signal') or '观望',
            'status': payload.get('status') or 'running',
            'confidence': payload.get('confidence'),
            'note': payload.get('note') or '',
            'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        _AI_TRADE_RUNS.insert(0, item)
        return item
