"""交易服务：封装长桥资金/持仓/订单，并提供异步持久化通知与专业动量回测。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from module_market.dao.market_dao import MarketInstrumentDao
from module_market.entity.vo.market_vo import KlineQueryModel
from module_market.service.index_session import is_live_kline_session, kline_session_tag
from module_market.service.kline_period import is_minute_period, normalize_kline_period
from module_quant.service.longbridge_quote import (
    is_cn_market,
    kline_high_low,
    merge_position_quotes,
    merge_snapshot_with_db,
)
from module_quant.service.longbridge_service import LongbridgeService
from module_trade.dao.trade_dao import TradeDao
from module_trade.service.auto_trade_service import parse_symbol_market
from utils.log_util import logger
from utils.quote_util import build_quote_from_klines

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# 回测最少K线数量与默认回看天数
_BACKTEST_MIN_BARS = 30
_BACKTEST_MIN_DAYS = 30
# 计算胜率所需的最少成交记录数（一买一卖记 2）
_MIN_TRADES_FOR_WINRATE = 2
_CLOSED_DAILY_KLINE_MSG = '已收盘，显示当日日K'


class TradeService:
    """Trade Service using standard DAO pattern and async operations"""

    @classmethod
    async def _ensure(cls, query_db: AsyncSession, user_id: int | None = None) -> None:
        await LongbridgeService.ensure_credentials_from_db(query_db, user_id)

    @classmethod
    async def get_account_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        return await LongbridgeService.get_account_balance_async()

    @classmethod
    async def get_positions_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        await cls._ensure(query_db)
        data = await LongbridgeService.get_positions_async()
        positions = list(data.get('positions') or [])
        symbols = [str(p.get('symbol') or '').strip() for p in positions if p.get('symbol')]
        if not symbols:
            return data
        try:
            quotes_res = await LongbridgeService.get_realtime_quote_async(symbols)
            merged = merge_position_quotes(positions, quotes_res.get('quotes') or [])
            return {**data, 'positions': merged, 'quotesSource': 'longbridge'}
        except Exception as exc:
            logger.warning(f'[trade] 持仓叠加长桥行情失败: {exc}')
            return data

    @classmethod
    async def get_realtime_quotes_services(
        cls,
        query_db: AsyncSession,
        symbols: list[str],
        market: str = 'US',
    ) -> dict[str, Any]:
        await cls._ensure(query_db)
        raw = [str(s).strip() for s in symbols if str(s).strip()]
        if not raw:
            return {'configured': True, 'quotes': [], 'message': '标的列表为空'}
        return await LongbridgeService.get_realtime_quote_async(raw, market)

    @classmethod
    async def get_orders_services(cls, query_db: AsyncSession, scope: str = 'today') -> dict[str, Any]:
        await cls._ensure(query_db)
        if scope == 'history':
            return await LongbridgeService.get_history_orders_async(100)
        return await LongbridgeService.get_today_orders_async()

    @classmethod
    async def get_order_services(cls, query_db: AsyncSession, order_id: str) -> dict[str, Any]:
        await cls._ensure(query_db)
        return await LongbridgeService.get_order_async(order_id)

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
    async def get_quote_snapshot_services(
        cls, query_db: AsyncSession, symbol: str, market: str = 'US'
    ) -> dict[str, Any]:
        """终端低频快照：库字段补空缺，估值/换手/量比/市值走长桥 calc_indexes。"""
        code, mkt = parse_symbol_market(symbol, market)
        await cls._ensure(query_db)
        if is_cn_market(mkt, code):
            snap: dict[str, Any] = {
                'configured': LongbridgeService.is_configured(),
                'available': False,
                'symbol': code,
                'market': 'CN',
                'reason': 'cn_no_depth',
                'message': 'A股基本面使用时序库与日K',
            }
        else:
            snap = await LongbridgeService.get_quote_snapshot_async(code, mkt)
        db_fields = await cls._db_snapshot_fields(query_db, code, mkt)
        return merge_snapshot_with_db(snap, db_fields)

    @classmethod
    async def _db_snapshot_fields(
        cls, query_db: AsyncSession, symbol: str, market: str
    ) -> dict[str, Any]:
        """名称/分类/历史高低来自 MySQL；A 股 OHLC 来自时序库。"""
        out: dict[str, Any] = {}
        try:
            inst = await MarketInstrumentDao.get_by_symbol(query_db, symbol)
            if inst is not None:
                if inst.name:
                    out['name'] = inst.name
                if inst.category:
                    out['category'] = inst.category
        except Exception as exc:
            logger.info(f'[snapshot] 标的元数据跳过 {symbol}: {exc}')
        try:
            extremes = await MarketInstrumentDao.price_extremes(query_db, symbol)
            out.update({k: v for k, v in extremes.items() if v is not None})
        except Exception as exc:
            logger.info(f'[snapshot] 日K极值跳过 {symbol}: {exc}')
        if not is_cn_market(market, symbol):
            return out
        try:
            from module_market.service.market_service import MarketService  # 缩短模块导入链

            klines = await MarketService.get_kline_services(
                KlineQueryModel(symbol=symbol, market='CN', period='daily')
            )
            quote = build_quote_from_klines(klines or [])
            out.update({key: val for key, val in quote.items() if val is not None})
            if klines:
                high52, low52 = kline_high_low(list(klines)[-260:])
                if high52 is not None:
                    out.setdefault('high52', high52)
                if low52 is not None:
                    out.setdefault('low52', low52)
                hist_high, hist_low = kline_high_low(list(klines))
                if hist_high is not None:
                    out.setdefault('historyHigh', hist_high)
                if hist_low is not None:
                    out.setdefault('historyLow', hist_low)
        except Exception as exc:
            logger.info(f'[snapshot] A股时序库跳过 {symbol}: {exc}')
        return out

    @classmethod
    async def _influx_klines(cls, code: str, mkt: str, period_key: str) -> list[dict[str, Any]]:
        from module_market.service.market_service import MarketService  # 缩短模块导入链

        rows = await MarketService.get_kline_services(KlineQueryModel(symbol=code, market=mkt, period=period_key))
        return list(rows or [])

    @classmethod
    async def _longbridge_minute_klines(cls, code: str, mkt: str, period_key: str, limit: int) -> list[dict[str, Any]]:
        try:
            market = str(mkt or '').upper()
            if market == 'US':
                # 美股 intraday 只有当前盘前；夜盘/昨盘后必须用 1 分钟 candlesticks（TradeSessions.All）
                fetch_period = '1min' if period_key == 'intraday' else period_key
                fetch_limit = min(1000, max(int(limit or 200), 500))
                cs = await LongbridgeService.get_candlesticks_async(code, mkt, fetch_period, fetch_limit)
                bars = list(cs.get('klines') or [])
                if bars:
                    return bars
                intra = await LongbridgeService.get_intraday_async(code, mkt)
                return list(intra.get('klines') or [])
            if period_key == 'intraday':
                intra = await LongbridgeService.get_intraday_async(code, mkt)
                return list(intra.get('klines') or [])
            cs = await LongbridgeService.get_candlesticks_async(code, mkt, period_key, limit)
            return list(cs.get('klines') or [])
        except Exception as exc:
            logger.info(f'[交易台K线] 长桥分钟/分时跳过: {exc}')
            return []

    @classmethod
    async def _resolve_quote_klines(
        cls,
        code: str,
        mkt: str,
        period_key: str,
        limit: int,
        lb_configured: bool,
    ) -> tuple[list[dict[str, Any]], str, str | None, str | None]:
        """日/周/月只用时序库；分钟盘中长桥优先，收盘回退当日日K。不补造。"""
        if not is_minute_period(period_key):
            return await cls._influx_klines(code, mkt, period_key), 'influx', None, None
        if not is_live_kline_session(mkt):
            bars = await cls._influx_klines(code, mkt, 'daily')
            return bars, 'influx', 'daily', _CLOSED_DAILY_KLINE_MSG
        if lb_configured and not str(code).startswith('^'):
            lb_bars = await cls._longbridge_minute_klines(code, mkt, period_key, limit)
            if lb_bars:
                return lb_bars, 'longbridge', None, None
        return await cls._influx_klines(code, mkt, period_key), 'influx', None, None

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
        交易台 K 线：日/周/月只用时序库；分时/分钟盘中优先长桥真实序列，收盘显示当日日K。
        """
        code, mkt = parse_symbol_market(symbol, market)
        period_key = normalize_kline_period(period)
        limit = max(20, min(int(limit or 200), 500))
        if mkt == 'US' and is_minute_period(period_key):
            limit = max(limit, 500)
        await cls._ensure(query_db)

        lb_configured = LongbridgeService.is_configured()
        session = kline_session_tag(mkt)
        klines, source, fallback, message = await cls._resolve_quote_klines(code, mkt, period_key, limit, lb_configured)

        if not klines and not message:
            message = '暂无K线'

        if klines and len(klines) > limit:
            klines = klines[-limit:]

        quote = cls._quote_from_klines(klines)
        price_source = 'history' if source == 'influx' else source
        # 日/周/月与已有 K 均跳过 QuoteContext.quote（~4s）；仅盘中分钟且库空时补最新价。
        if (
            not klines
            and source != 'longbridge'
            and lb_configured
            and is_minute_period(period_key)
            and is_live_kline_session(mkt)
            and mkt in {'US', 'HK'}
            and not str(code).startswith('^')
        ):
            try:
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
            except Exception as exc:
                logger.info(f'[交易台K线] 长桥实时价跳过: {exc}')

        out: dict[str, Any] = {
            'symbol': code,
            'market': mkt,
            'period': period_key,
            'source': source,
            'priceSource': price_source,
            'configured': lb_configured,
            'message': message,
            'session': session,
            'klines': klines,
            'quote': {**quote, 'source': price_source} if quote else {},
        }
        if fallback:
            out['fallback'] = fallback
        return out

    @staticmethod
    def _quote_from_klines(klines: list[dict[str, Any]]) -> dict[str, Any]:
        # 统一走公共实现，与 market 侧保持一致
        return build_quote_from_klines(klines)

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
            allow_sim=True,
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
        result = await LongbridgeService.cancel_order_async(order_id, allow_sim=True)
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
            InfluxUtil.query_klines, market, symbol, f'-{max(days, _BACKTEST_MIN_DAYS)}d', 'now()'
        )
        if not klines or len(klines) < _BACKTEST_MIN_BARS:
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
        win_rate = round((winning_trades / (trades // 2) * 100), 2) if (trades >= _MIN_TRADES_FOR_WINRATE) else 0.0
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
        result = [
            {
                'id': b.batch_id,
                'cycleId': b.cycle_id,
                'symbolsCount': b.symbols_count,
                'successCount': b.success_count,
                'status': 'completed' if b.status == '1' else ('running' if b.status == '0' else 'failed'),
                'summary': b.summary,
                'createTime': b.create_time.strftime('%Y-%m-%d %H:%M:%S') if b.create_time else '',
            }
            for b in batch_runs
        ]
        return result
