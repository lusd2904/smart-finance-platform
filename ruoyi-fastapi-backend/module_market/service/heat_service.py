"""
市场热度看板：收盘后采集指数/成交额/A-D，生成 Top50 快照与规则化热度摘要。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from module_market.config.heat_config import (
    DEFAULT_HEAT_WEIGHTS,
    MARKET_META,
    VALID_MARKETS,
    WEIGHT_CONFIG_KEYS,
)
from module_market.dao.heat_dao import MarketHeatDao
from module_market.dao.market_dao import MarketInstrumentDao, MarketWatchlistDao
from module_market.entity.vo.market_vo import MarketInstrumentQueryModel
from module_quant.service.longbridge_service import LongbridgeService
from utils.influx_util import InfluxUtil
from utils.log_util import logger
from utils.longbridge_breaker import LongbridgeBreaker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

WEEKEND_WEEKDAY = 5
ACTIVE_HEAT_SCORE = 70.0
COLD_HEAT_SCORE = 35.0
MIN_KLINES_FOR_CHANGE = 2
ADVANCE_CHANGE_THRESHOLD = 0.05
DECLINE_CHANGE_THRESHOLD = -0.05


def _normalize_market(market: str | None) -> str:
    code = str(market or 'US').strip().upper()
    if code not in VALID_MARKETS:
        raise ValueError(f'不支持的市场: {market}')
    return code


def _today_in_market(market: str) -> str:
    tz = ZoneInfo(str(MARKET_META[market]['timezone']))
    return datetime.now(tz).strftime('%Y-%m-%d')


def _is_weekday(date_str: str) -> bool:
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return False
    return dt.weekday() < WEEKEND_WEEKDAY


def _resolve_trade_date(market: str, trade_date: str | None) -> str:
    if trade_date:
        return str(trade_date)[:10]
    return _today_in_market(market)


def _clamp_score(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _index_score(change_pct: float | None) -> float:
    if change_pct is None:
        return 50.0
    return _clamp_score(50.0 + change_pct * 8.0)


def _turnover_score(total_turnover: float | None, baseline: float | None) -> float:
    if not total_turnover or total_turnover <= 0:
        return 40.0
    if not baseline or baseline <= 0:
        return _clamp_score(min(100.0, 40.0 + total_turnover / 1e10))
    ratio = total_turnover / baseline
    return _clamp_score(30.0 + min(ratio, 2.5) * 28.0)


def _advance_decline_score(advance: int, decline: int) -> float:
    total = advance + decline
    if total <= 0:
        return 50.0
    ratio = advance / total
    return _clamp_score(ratio * 100.0)


def _heat_summary(score: float, market: str, index_change: float | None, advance: int, decline: int) -> str:
    label = MARKET_META[market]['label']
    trend = '震荡'
    if index_change is not None:
        if index_change >= 1.0:
            trend = '偏强'
        elif index_change <= -1.0:
            trend = '偏弱'
    breadth = '涨跌均衡'
    if advance > decline * 1.2:
        breadth = '普涨'
    elif decline > advance * 1.2:
        breadth = '普跌'
    level = '中性'
    if score >= ACTIVE_HEAT_SCORE:
        level = '活跃'
    elif score <= COLD_HEAT_SCORE:
        level = '偏冷'
    idx_text = f'指数{index_change:+.2f}%' if index_change is not None else '指数待更新'
    return f'{label}{trend}，{idx_text}，{breadth}（涨{advance}/跌{decline}），热度{level}。'


class MarketHeatService:
    @classmethod
    async def resolve_weights(cls) -> dict[str, float]:
        weights = dict(DEFAULT_HEAT_WEIGHTS)
        try:
            from config.get_redis import RedisUtil

            redis = RedisUtil.get_client()
            if redis is not None:
                for config_key, field in WEIGHT_CONFIG_KEYS.items():
                    raw = await redis.get(f'sys_config:{config_key}')
                    if raw is not None and str(raw).strip() != '':
                        weights[field] = float(raw)
        except Exception as exc:
            logger.info(f'[热度] 读取 sys_config 权重失败，使用默认: {exc}')
        total = sum(weights.values()) or 1.0
        return {k: round(v / total, 4) for k, v in weights.items()}

    @classmethod
    async def get_config_services(cls) -> dict[str, Any]:
        weights = await cls.resolve_weights()
        markets = {
            code: {
                'label': meta['label'],
                'currency': meta['currency'],
                'indexSymbol': meta['index_symbol'],
                'indexName': meta['index_name'],
                'capFilterRule': meta['cap_rule'],
            }
            for code, meta in MARKET_META.items()
        }
        return {'weights': weights, 'markets': markets, 'configKeys': list(WEIGHT_CONFIG_KEYS.keys())}

    @classmethod
    async def _universe_symbols(cls, db: AsyncSession, market: str) -> list[tuple[str, str]]:
        query = MarketInstrumentQueryModel(market=market, enabled='1')
        rows = await MarketInstrumentDao.get_instrument_list(db, query)
        out: list[tuple[str, str]] = []
        for row in rows:
            if (row.category or '').lower() == 'index':
                continue
            out.append((row.symbol, row.name or row.symbol))
        if out:
            return out
        from module_market.constant.instruments import TARGET_INSTRUMENTS

        for symbol, name, mkt, category in TARGET_INSTRUMENTS:
            if mkt == market and category != 'index':
                out.append((symbol, name))
        return out

    @classmethod
    def _quote_map_from_longbridge(cls, market: str, symbols: list[str]) -> dict[str, dict[str, Any]]:
        lb_symbols = [LongbridgeService.to_longbridge_symbol(sym, market) for sym in symbols]
        res = LongbridgeService.get_realtime_quote(lb_symbols)
        mapping: dict[str, dict[str, Any]] = {}
        for quote in res.get('quotes') or []:
            sym = str(quote.get('symbol') or '')
            clean = sym.split('.', maxsplit=1)[0] if market != 'US' else sym.replace('.US', '').replace('.HK', '')
            if market == 'HK' and '.HK' in sym:
                clean = sym
            mapping[clean.upper()] = quote
            mapping[sym.upper()] = quote
        return mapping

    @classmethod
    def _static_info_map(cls, market: str, symbols: list[str]) -> dict[str, dict[str, Any]]:
        lb_symbols = [LongbridgeService.to_longbridge_symbol(sym, market) for sym in symbols]
        res = LongbridgeService.get_static_info(lb_symbols)
        mapping: dict[str, dict[str, Any]] = {}
        for item in res.get('items') or []:
            sym = str(item.get('symbol') or '')
            clean = sym.split('.', maxsplit=1)[0] if market != 'US' else sym.replace('.US', '').replace('.HK', '')
            if market == 'HK' and '.HK' in sym:
                clean = sym
            mapping[clean.upper()] = item
            mapping[sym.upper()] = item
        return mapping

    @classmethod
    def _index_change_from_influx(cls, market: str, symbol: str) -> float | None:
        klines = InfluxUtil.query_klines(market, symbol, '-30d', 'now()', 3)
        if len(klines) < MIN_KLINES_FOR_CHANGE:
            return None
        prev = klines[-2]
        last = klines[-1]
        prev_close = prev.get('close')
        last_close = last.get('close')
        if not prev_close or not last_close:
            return None
        return round((float(last_close) / float(prev_close) - 1.0) * 100, 4)

    @classmethod
    def filter_top50_candidates(
        cls,
        market: str,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        meta = MARKET_META[market]
        cap_min = float(meta['cap_min'])
        cap_max = float(meta['cap_max'])
        filtered = [
            item
            for item in candidates
            if item.get('turnover') and item['turnover'] > 0
            and item.get('market_cap') is not None
            and cap_min <= float(item['market_cap']) <= cap_max
        ]
        filtered.sort(key=lambda x: float(x.get('turnover') or 0), reverse=True)
        top = filtered[:50]
        for idx, item in enumerate(top, start=1):
            item['rankNo'] = idx
        return top

    @classmethod
    def compute_heat_score(
        cls,
        weights: dict[str, float],
        index_change: float | None,
        total_turnover: float | None,
        advance: int,
        decline: int,
        turnover_baseline: float | None = None,
    ) -> float:
        parts = {
            'index': _index_score(index_change),
            'turnover': _turnover_score(total_turnover, turnover_baseline),
            'advance_decline': _advance_decline_score(advance, decline),
        }
        score = sum(parts[key] * weights.get(key, 0.0) for key in parts)
        return round(_clamp_score(score), 2)

    @classmethod
    async def collect_market(cls, db: AsyncSession, market: str, trade_date: str | None = None) -> dict[str, Any]:  # noqa: PLR0915
        market = _normalize_market(market)
        session_date = _resolve_trade_date(market, trade_date)
        if not _is_weekday(session_date):
            return {'skipped': True, 'market': market, 'tradeDate': session_date, 'reason': 'non_trading_day'}

        if not LongbridgeBreaker.allow():
            return {
                'skipped': True,
                'market': market,
                'tradeDate': session_date,
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
            }

        await LongbridgeService.ensure_credentials_from_db(db)
        meta = MARKET_META[market]
        weights = await cls.resolve_weights()
        universe = await cls._universe_symbols(db, market)
        symbols = [sym for sym, _name in universe]
        name_map = dict(universe)

        loop = asyncio.get_running_loop()
        quote_map, static_map = await asyncio.gather(
            loop.run_in_executor(None, cls._quote_map_from_longbridge, market, symbols),
            loop.run_in_executor(None, cls._static_info_map, market, symbols),
        )

        candidates: list[dict[str, Any]] = []
        advance = decline = flat = 0
        total_turnover = 0.0
        for symbol in symbols:
            quote = quote_map.get(symbol.upper()) or quote_map.get(symbol) or {}
            static = static_map.get(symbol.upper()) or static_map.get(symbol) or {}
            price = quote.get('lastDone') or quote.get('last') or quote.get('close') or quote.get('price')
            shares = static.get('totalShares') or static.get('circulatingShares')
            market_cap = None
            if price is not None and shares:
                market_cap = float(price) * float(shares)
            turnover = quote.get('turnover')
            change_pct = quote.get('changeRate')
            if change_pct is None:
                change_pct = quote.get('change')
            if change_pct is not None:
                if change_pct > ADVANCE_CHANGE_THRESHOLD:
                    advance += 1
                elif change_pct < DECLINE_CHANGE_THRESHOLD:
                    decline += 1
                else:
                    flat += 1
            if turnover:
                total_turnover += float(turnover)
            candidates.append(
                {
                    'symbol': symbol,
                    'name': static.get('name') or name_map.get(symbol) or symbol,
                    'marketCap': market_cap,
                    'turnover': float(turnover) if turnover else None,
                    'changePct': float(change_pct) if change_pct is not None else None,
                    'currency': meta['currency'],
                }
            )

        index_change = await loop.run_in_executor(
            None, cls._index_change_from_influx, market, str(meta['index_symbol'])
        )
        if index_change is None:
            idx_quote = quote_map.get(str(meta['index_symbol']).upper()) or {}
            index_change = idx_quote.get('changeRate') or idx_quote.get('change')

        trend_rows = await MarketHeatDao.list_heat_trend(db, market, limit=5)
        baseline = None
        if trend_rows:
            vals = [float(r.total_turnover) for r in trend_rows if r.total_turnover]
            baseline = sum(vals) / len(vals) if vals else None

        top50 = cls.filter_top50_candidates(
            market,
            [
                {
                    'symbol': c['symbol'],
                    'name': c['name'],
                    'market_cap': c['marketCap'],
                    'turnover': c['turnover'],
                    'change_pct': c['changePct'],
                    'currency': c['currency'],
                }
                for c in candidates
            ],
        )
        heat_score = cls.compute_heat_score(weights, index_change, total_turnover, advance, decline, baseline)
        summary = _heat_summary(heat_score, market, index_change, advance, decline)
        as_of = datetime.now()
        status = 'ok' if top50 else 'empty'
        message = None if top50 else '样本池内无符合市值区间的成交额数据'

        await MarketHeatDao.upsert_heat(
            db,
            {
                'market': market,
                'trade_date': session_date,
                'index_symbol': meta['index_symbol'],
                'index_name': meta['index_name'],
                'index_change_pct': index_change,
                'total_turnover': total_turnover or None,
                'advance_count': advance,
                'decline_count': decline,
                'flat_count': flat,
                'heat_score': heat_score,
                'heat_summary': summary,
                'currency': meta['currency'],
                'filter_rule': meta['cap_rule'],
                'weights_json': json.dumps(weights, ensure_ascii=False),
                'as_of_time': as_of,
                'status': status,
                'message': message,
                'create_time': as_of,
                'update_time': as_of,
            },
        )
        await MarketHeatDao.replace_top50(
            db,
            market,
            session_date,
            [
                {
                    'market': market,
                    'trade_date': session_date,
                    'rank_no': item['rankNo'],
                    'symbol': item['symbol'],
                    'name': item['name'],
                    'market_cap': item['market_cap'],
                    'turnover': item['turnover'],
                    'change_pct': item['change_pct'],
                    'currency': item['currency'],
                    'as_of_time': as_of,
                    'create_time': as_of,
                }
                for item in top50
            ],
        )
        await db.commit()
        return {
            'market': market,
            'tradeDate': session_date,
            'heatScore': heat_score,
            'top50Count': len(top50),
            'status': status,
            'asOfTime': as_of.strftime('%Y-%m-%d %H:%M:%S'),
        }

    @classmethod
    def _serialize_heat(cls, row: Any, stale_hours: int = 36) -> dict[str, Any]:
        as_of = row.as_of_time
        stale = False
        if as_of and datetime.now() - as_of > timedelta(hours=stale_hours):
            stale = True
        return {
            'market': row.market,
            'tradeDate': row.trade_date,
            'indexSymbol': row.index_symbol,
            'indexName': row.index_name,
            'indexChangePct': row.index_change_pct,
            'totalTurnover': row.total_turnover,
            'advanceCount': row.advance_count,
            'declineCount': row.decline_count,
            'flatCount': row.flat_count,
            'heatScore': row.heat_score,
            'heatSummary': row.heat_summary,
            'currency': row.currency,
            'filterRule': row.filter_rule,
            'weights': json.loads(row.weights_json or '{}') if row.weights_json else {},
            'asOfTime': row.as_of_time.strftime('%Y-%m-%d %H:%M:%S') if row.as_of_time else None,
            'status': 'stale' if stale and row.status == 'ok' else row.status,
            'message': row.message,
            'staleHint': '数据可能不是最新收盘快照，请选择其他交易日或等待任务刷新。' if stale else None,
        }

    @classmethod
    def _serialize_top50(cls, rows: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                'rankNo': row.rank_no,
                'symbol': row.symbol,
                'name': row.name,
                'marketCap': row.market_cap,
                'turnover': row.turnover,
                'changePct': row.change_pct,
                'currency': row.currency,
                'asOfTime': row.as_of_time.strftime('%Y-%m-%d %H:%M:%S') if row.as_of_time else None,
            }
            for row in rows
        ]

    @classmethod
    async def get_daily_services(
        cls,
        db: AsyncSession,
        market: str,
        trade_date: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        market = _normalize_market(market)
        session_date = trade_date[:10] if trade_date else None
        heat_row = None
        if session_date:
            heat_row = await MarketHeatDao.get_heat(db, market, session_date)
        else:
            heat_row = await MarketHeatDao.get_latest_heat(db, market)
            session_date = heat_row.trade_date if heat_row else _resolve_trade_date(market, None)

        if not heat_row:
            return {
                'market': market,
                'tradeDate': session_date,
                'empty': True,
                'loadingHint': '暂无该日热度快照，收盘任务完成后将自动写入。',
                'heat': None,
                'top50': [],
                'meta': MARKET_META[market],
            }

        top50_rows = await MarketHeatDao.list_top50(db, market, heat_row.trade_date)
        watchlist = await MarketWatchlistDao.get_enabled(db, user_id=user_id) if user_id else []
        watch_set = {(w.symbol.upper(), (w.market or 'US').upper()) for w in watchlist}
        top50 = cls._serialize_top50(top50_rows)
        for item in top50:
            item['inWatchlist'] = (item['symbol'].upper(), market) in watch_set

        return {
            'market': market,
            'tradeDate': heat_row.trade_date,
            'empty': False,
            'heat': cls._serialize_heat(heat_row),
            'top50': top50,
            'meta': {
                'label': MARKET_META[market]['label'],
                'currency': MARKET_META[market]['currency'],
                'capFilterRule': MARKET_META[market]['cap_rule'],
            },
        }

    @classmethod
    async def get_trend_services(cls, db: AsyncSession, market: str, days: int = 5) -> dict[str, Any]:
        market = _normalize_market(market)
        rows = await MarketHeatDao.list_heat_trend(db, market, limit=days)
        points = [
            {
                'tradeDate': row.trade_date,
                'indexChangePct': row.index_change_pct,
                'totalTurnover': row.total_turnover,
                'heatScore': row.heat_score,
                'advanceCount': row.advance_count,
                'declineCount': row.decline_count,
            }
            for row in rows
        ]
        return {'market': market, 'days': days, 'points': points}

    @classmethod
    async def list_available_dates(cls, db: AsyncSession, market: str, limit: int = 30) -> list[str]:
        rows = await MarketHeatDao.list_heat_trend(db, market, limit=limit)
        return [row.trade_date for row in reversed(rows)]
