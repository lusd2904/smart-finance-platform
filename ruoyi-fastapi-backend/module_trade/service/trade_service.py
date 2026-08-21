"""交易服务：封装长桥资金/持仓/订单，并提供异步持久化通知与专业动量回测。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_market.entity.vo.market_vo import KlineQueryModel
from module_market.service.kline_period import is_minute_period, normalize_kline_period
from module_market.service.market_service import MarketService
from module_quant.service.longbridge_service import LongbridgeService
from module_trade.dao.trade_dao import TradeDao
from module_trade.service.auto_trade_service import parse_symbol_market
from utils.log_util import logger


class TradeService:
    """Trade Service using standard DAO pattern and async operations"""

    @classmethod
    async def _ensure(cls, query_db: AsyncSession) -> None:
        await LongbridgeService.ensure_credentials_from_db(query_db)

    @classmethod
    async def get_account_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        return await LongbridgeService.get_account_balance_async()

    @classmethod
    async def get_positions_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        return await LongbridgeService.get_positions_async()

    @classmethod
    async def get_orders_services(cls, query_db: AsyncSession, scope: str = 'today') -> dict[str, Any]:
        await cls._ensure(query_db)
        if scope == 'history':
            return await LongbridgeService.get_history_orders_async(100)
        return await LongbridgeService.get_today_orders_async()

    @classmethod
    async def get_depth_services(cls, query_db: AsyncSession, symbol: str, market: str = 'US') -> dict[str, Any]:
        code, mkt = parse_symbol_market(symbol, market)
        await cls._ensure(query_db)
        return await LongbridgeService.get_depth_async(code, mkt)

    @classmethod
    async def get_trades_services(
        cls, query_db: AsyncSession, symbol: str, market: str = 'US', count: int = 30
    ) -> dict[str, Any]:
        code, mkt = parse_symbol_market(symbol, market)
        await cls._ensure(query_db)
        return await LongbridgeService.get_trades_async(code, mkt, count)

    @classmethod
    async def get_quote_kline_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        period: str = 'daily',
        limit: int = 200,
    ) -> dict[str, Any]:
        """
        交易台 K 线：优先 Influx 真实序列；US/HK 分钟/分时在时序库为空时回退长桥 candlesticks/intraday。
        Influx 已有 K 时不再额外打长桥实时报价；仅在无历史 bar 时取 lastDone，不新增、不补空。
        """
        code, mkt = parse_symbol_market(symbol, market)
        period_key = normalize_kline_period(period)
        limit = max(20, min(int(limit or 200), 500))
        await cls._ensure(query_db)

        influx_klines = await MarketService.get_kline_services(
            KlineQueryModel(symbol=code, market=mkt, period=period_key)
        )
        source = 'influx'
        klines = list(influx_klines or [])
        message = None

        if not klines and is_minute_period(period_key) and mkt in {'US', 'HK'} and LongbridgeService.is_configured():
            if period_key == 'intraday':
                lb = await LongbridgeService.get_intraday_async(code, mkt)
            else:
                lb = await LongbridgeService.get_candlesticks_async(code, mkt, period_key, limit)
            klines = list(lb.get('klines') or [])
            if klines:
                source = 'longbridge'
            else:
                message = lb.get('message') or '暂无K线'

        if not klines and not message:
            message = '暂无K线'

        if klines and len(klines) > limit:
            klines = klines[-limit:]

        quote = cls._quote_from_klines(klines)
        price_source = 'history'
        # Influx already has real bars: skip the extra QuoteContext.quote (~4s).
        # Live lastDone is only fetched when history is empty (or Longbridge fallback bars).
        if (
            not influx_klines
            and LongbridgeService.is_configured()
            and mkt in {'US', 'HK'}
            and not str(code).startswith('^')
        ):
            rt = await LongbridgeService.get_realtime_quote_async([code], mkt)
            quotes = rt.get('quotes') or []
            if quotes:
                q0 = quotes[0]
                last = q0.get('lastDone')
                quote = {
                    **quote,
                    'last': last if last is not None else quote.get('last'),
                    'open': q0.get('open') if q0.get('open') is not None else quote.get('open'),
                    'high': q0.get('high') if q0.get('high') is not None else quote.get('high'),
                    'low': q0.get('low') if q0.get('low') is not None else quote.get('low'),
                    'volume': q0.get('volume') if q0.get('volume') is not None else quote.get('volume'),
                    'change': q0.get('change'),
                    'changeRate': q0.get('changeRate'),
                    'prevClose': q0.get('prevClose'),
                }
                price_source = 'longbridge'
                if klines and last is not None:
                    LongbridgeService.overlay_last_bar(klines[-1], float(last))

        return {
            'symbol': code,
            'market': mkt,
            'period': period_key,
            'source': source,
            'priceSource': price_source,
            'configured': LongbridgeService.is_configured(),
            'message': message,
            'klines': klines,
            'quote': {**quote, 'source': price_source} if quote else {},
        }

    @staticmethod
    def _quote_from_klines(klines: list[dict[str, Any]]) -> dict[str, Any]:
        if not klines:
            return {}
        last = klines[-1]
        prev = klines[-2] if len(klines) > 1 else None
        change = change_rate = None
        try:
            if prev and prev.get('close') and last.get('close'):
                change = round(float(last['close']) - float(prev['close']), 4)
                change_rate = round(change / float(prev['close']) * 100, 4)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return {
            'last': last.get('close'),
            'open': last.get('open'),
            'high': last.get('high'),
            'low': last.get('low'),
            'volume': last.get('volume'),
            'tradeDate': last.get('date'),
            'change': change,
            'changeRate': change_rate,
            'prevClose': prev.get('close') if prev else None,
        }

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
        result = await LongbridgeService.submit_order_async(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            market=market,
        )
        await cls.push_notification_db(
            query_db,
            title=f'下单{"成功" if result.get("ok") else "失败"}',
            content=f'{side} {symbol} x {quantity} · {result.get("message")}',
            level='success' if result.get('ok') else 'danger',
            category='trade',
        )
        return result

    @classmethod
    async def cancel_order_services(cls, query_db: AsyncSession, order_id: str) -> dict[str, Any]:
        await cls._ensure(query_db)
        result = await LongbridgeService.cancel_order_async(order_id)
        await cls.push_notification_db(
            query_db,
            title=f'撤单{"成功" if result.get("ok") else "失败"}',
            content=f'订单 {order_id} · {result.get("message")}',
            level='warning' if result.get('ok') else 'danger',
            category='trade',
        )
        return result

    # ---------- 持久化通知 ----------
    @classmethod
    async def push_notification_db(
        cls,
        query_db: AsyncSession,
        title: str,
        content: str,
        level: str = 'info',
        category: str = 'system',
    ) -> dict[str, Any]:
        try:
            item = await TradeDao.add_notification(
                query_db,
                {'title': title, 'content': content, 'level': level, 'category': category},
            )
            await query_db.commit()
            return {
                'id': item.notice_id,
                'title': item.title,
                'content': item.content,
                'level': item.level,
                'category': item.category,
                'read': item.is_read == '1',
                'createTime': item.create_time.strftime('%Y-%m-%d %H:%M:%S') if item.create_time else '',
            }
        except Exception as e:
            logger.warning(f'[通知持久化] 写入通知失败: {e}')
            return {
                'id': int(datetime.now().timestamp() * 1000),
                'title': title,
                'content': content,
                'level': level,
                'category': category,
                'read': False,
                'createTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

    @classmethod
    async def list_notifications_services(cls, query_db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        rows = await TradeDao.list_notifications(query_db, limit=limit)
        return [
            {
                'id': r.notice_id,
                'title': r.title,
                'content': r.content,
                'level': r.level,
                'category': r.category,
                'read': r.is_read == '1',
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else '',
            }
            for r in rows
        ]

    @classmethod
    async def mark_notification_read_services(
        cls, query_db: AsyncSession, notice_id: int | None = None
    ) -> dict[str, Any]:
        updated = await TradeDao.mark_notifications_read(query_db, notice_id)
        await query_db.commit()
        return {'updated': updated}

    # ---------- 量化回测引擎（支持滑点、手续费、最大回撤与胜率） ----------
    @classmethod
    async def run_backtest_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        days: int = 120,
        initial_capital: float = 100000.0,
        fee_rate: float = 0.0005,
        slippage: float = 0.0002,
    ) -> dict[str, Any]:
        from utils.influx_util import InfluxUtil

        klines = await asyncio.to_thread(
            InfluxUtil.query_klines, market, symbol, f'-{max(days, 30)}d', 'now()'
        )
        if not klines or len(klines) < 30:
            return {
                'ok': False,
                'message': f'{symbol} K线不足，请先同步行情',
                'symbol': symbol,
            }

        closes = [float(k.get('close') or 0) for k in klines]
        cash = initial_capital
        pos = 0.0
        equity_curve: list[dict[str, Any]] = []
        trades = 0
        winning_trades = 0
        last_buy_price = 0.0
        peak_equity = initial_capital
        max_drawdown = 0.0

        for i in range(20, len(closes)):
            ma5 = sum(closes[i - 5 : i]) / 5
            ma20 = sum(closes[i - 20 : i]) / 20
            price = closes[i]
            if price <= 0:
                continue

            # 金叉买入 (MA5 > MA20)
            if ma5 > ma20 and pos == 0 and cash > 0:
                exec_price = price * (1 + slippage)
                cost_with_fee = exec_price * (1 + fee_rate)
                pos = cash / cost_with_fee
                last_buy_price = exec_price
                cash = 0.0
                trades += 1
            # 死叉卖出 (MA5 < MA20)
            elif ma5 < ma20 and pos > 0:
                exec_price = price * (1 - slippage)
                gross_proceeds = pos * exec_price
                cash = gross_proceeds * (1 - fee_rate)
                if exec_price > last_buy_price:
                    winning_trades += 1
                pos = 0.0
                trades += 1

            current_equity = cash + pos * price
            peak_equity = max(peak_equity, current_equity)
            dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
            max_drawdown = max(max_drawdown, dd)

            equity_curve.append({
                'date': klines[i].get('date'),
                'equity': round(current_equity, 2),
            })

        final_equity = cash + pos * closes[-1]
        ret_pct = round((final_equity / initial_capital - 1) * 100, 2)
        win_rate = round((winning_trades / (trades // 2) * 100), 2) if (trades >= 2) else 0.0
        max_dd_pct = round(max_drawdown * 100, 2)

        # 持久化到 DB
        db_record = {
            'symbol': symbol,
            'market': market,
            'days': days,
            'strategy': 'MA5/MA20 cross',
            'trades': trades,
            'return_pct': ret_pct,
            'final_equity': round(final_equity, 2),
            'max_drawdown': max_dd_pct,
            'win_rate': win_rate,
            'equity_curve_json': json.dumps(equity_curve[-60:], ensure_ascii=False),
            'message': '回测完成（标准动量双均线策略）',
        }
        saved = await TradeDao.add_backtest_run(query_db, db_record)
        await query_db.commit()

        # 推送持久化通知
        await cls.push_notification_db(
            query_db,
            title=f'回测完成 {symbol}',
            content=f'收益 {ret_pct}% · 最大回撤 {max_dd_pct}% · 交易 {trades} 次',
            level='success',
            category='backtest',
        )

        return {
            'id': saved.run_id,
            'symbol': symbol,
            'market': market,
            'days': days,
            'trades': trades,
            'returnPct': ret_pct,
            'finalEquity': round(final_equity, 2),
            'maxDrawdown': max_dd_pct,
            'winRate': win_rate,
            'equity': equity_curve[-60:],
            'createTime': saved.create_time.strftime('%Y-%m-%d %H:%M:%S') if saved.create_time else '',
            'strategy': saved.strategy,
            'ok': True,
            'message': saved.message,
        }

    @classmethod
    async def list_backtests_services(cls, query_db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        rows = await TradeDao.list_backtest_runs(query_db, limit=limit)
        result = []
        for r in rows:
            curve = []
            try:
                if r.equity_curve_json:
                    curve = json.loads(r.equity_curve_json)
            except Exception:
                curve = []
            result.append({
                'id': r.run_id,
                'symbol': r.symbol,
                'market': r.market,
                'days': r.days,
                'trades': r.trades,
                'returnPct': r.return_pct,
                'finalEquity': r.final_equity,
                'maxDrawdown': r.max_drawdown,
                'winRate': r.win_rate,
                'strategy': r.strategy,
                'points': len(curve),
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else '',
            })
        return result

    @classmethod
    async def get_backtest_services(cls, query_db: AsyncSession, run_id: int) -> dict[str, Any] | None:
        r = await TradeDao.get_backtest_run_by_id(query_db, run_id)
        if not r:
            return None
        curve = []
        try:
            if r.equity_curve_json:
                curve = json.loads(r.equity_curve_json)
        except Exception:
            curve = []
        return {
            'id': r.run_id,
            'symbol': r.symbol,
            'market': r.market,
            'days': r.days,
            'trades': r.trades,
            'returnPct': r.return_pct,
            'finalEquity': r.final_equity,
            'maxDrawdown': r.max_drawdown,
            'winRate': r.win_rate,
            'strategy': r.strategy,
            'equity': curve,
            'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else '',
            'message': r.message,
            'ok': True,
        }

    # ---------- AI 自动交易台账 ----------
    @classmethod
    async def list_ai_trade_runs(cls, query_db: AsyncSession) -> list[dict[str, Any]]:
        batch_runs = await TradeDao.list_ai_batch_runs(query_db, limit=20)
        if not batch_runs:
            now = datetime.now()
            return [
                {
                    'id': i + 1,
                    'symbol': sym,
                    'signal': '观望' if i else '买入',
                    'status': 'completed',
                    'confidence': 60 + i * 8,
                    'note': '示例台账（接入调度后替换为真实运行）',
                    'createTime': (now - timedelta(hours=i * 3)).strftime('%Y-%m-%d %H:%M:%S'),
                }
                for i, sym in enumerate(['AAPL', 'NVDA', 'MSFT'])
            ]
        result = []
        for b in batch_runs:
            result.append({
                'id': b.batch_id,
                'cycleId': b.cycle_id,
                'symbolsCount': b.symbols_count,
                'successCount': b.success_count,
                'status': 'completed' if b.status == '1' else ('running' if b.status == '0' else 'failed'),
                'summary': b.summary,
                'createTime': b.create_time.strftime('%Y-%m-%d %H:%M:%S') if b.create_time else '',
            })
        return result
