"""
行情中心自选清单：CRUD + 小时级综合分析（指标 / 长桥资讯 / 舆情）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_market.constant.instruments import get_instrument_meta
from module_market.dao.market_dao import (
    MarketInstrumentDao,
    MarketWatchlistAnalysisDao,
    MarketWatchlistDao,
)
from module_market.entity.vo.market_vo import (
    AddMarketWatchlistModel,
    MarketWatchlistAnalyzeModel,
    MarketWatchlistPageQueryModel,
)
from module_market.service.market_service import MarketService
from module_market.service.stock_pick_service import StockPickService
from utils.influx_util import InfluxUtil
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MAX_WATCHLIST_BATCH = 30
OVERVIEW_CACHE_TTL = 10
OVERVIEW_CACHE_PREFIX = 'market:watchlist:overview:'


async def _overview_cache_get(user_id: int) -> dict[str, Any] | None:
    try:
        cached = await cache_get_json(f'{OVERVIEW_CACHE_PREFIX}{user_id}')
    except Exception as exc:
        logger.debug(f'[自选] overview 缓存读取失败: {exc}')
        return None
    if isinstance(cached, dict) and 'items' in cached:
        return cached
    return None


async def _overview_cache_set(user_id: int, data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or 'items' not in data:
        return
    try:
        await cache_set_json(f'{OVERVIEW_CACHE_PREFIX}{user_id}', data, OVERVIEW_CACHE_TTL)
    except Exception as exc:
        logger.debug(f'[自选] overview 缓存写入失败: {exc}')


async def _overview_cache_clear(user_id: int | None) -> None:
    if not user_id:
        return
    try:
        from config.get_redis import RedisUtil

        redis = RedisUtil.get_client()
        if redis is None:
            return
        await redis.delete(f'{OVERVIEW_CACHE_PREFIX}{user_id}')
    except Exception as exc:
        logger.debug(f'[自选] overview 缓存失效失败: {exc}')


def _resolve_watchlist_name(symbol: str, market: str, stored_name: str | None = None) -> str:
    if stored_name:
        return stored_name
    meta = get_instrument_meta(symbol)
    if meta:
        return meta[1]
    return symbol


def parse_note_groups(note: str | None) -> list[str]:
    """note 里用逗号分隔分组名（兼容中文逗号）。空 note 不算分组。"""
    if not note:
        return []
    parts = [p.strip() for p in str(note).replace('，', ',').split(',')]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return seen


def _serialize_market_watchlist_row(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        symbol = str(row.get('symbol') or '')
        market = (row.get('market') or 'US').upper()
        note = row.get('note')
        return {
            **row,
            'market': market,
            'name': row.get('name') or _resolve_watchlist_name(symbol, market),
            'groups': parse_note_groups(note),
        }
    symbol = row.symbol
    market = (row.market or 'US').upper()
    note = row.note
    return {
        'id': row.id,
        'userId': row.user_id,
        'symbol': symbol,
        'market': market,
        'name': _resolve_watchlist_name(symbol, market, getattr(row, 'name', None)),
        'note': note,
        'groups': parse_note_groups(note),
        'enabled': row.enabled,
        'sortOrder': getattr(row, 'sort_order', 0) or 0,
        'createTime': _fmt_dt(row.create_time),
        'updateTime': _fmt_dt(getattr(row, 'update_time', None) or row.create_time),
    }


def _dump(payload: Any, limit: int = 60000) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)[:limit]


def _fmt_dt(value: datetime | None) -> str | None:
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


REC_SIGN = {
    '买入': 1,
    '加仓': 1,
    '减仓': -1,
    '卖出': -1,
}


def forward_returns_from_klines(
    klines: list[dict[str, Any]], as_of: str, horizons: tuple[int, ...] = (1, 5)
) -> dict[str, float | None]:
    """以 as_of 当日（或之前最近一根）收盘为基准，取之后 1/5 个交易日的涨跌幅（百分比）。"""
    as_of = str(as_of or '')[:10]
    dates: list[str] = []
    closes: list[float] = []
    for row in klines or []:
        day = str(row.get('date') or '')[:10]
        try:
            close = float(row.get('close'))
        except (TypeError, ValueError):
            continue
        if day:
            dates.append(day)
            closes.append(close)
    entry = None
    for i, day in enumerate(dates):
        if day <= as_of:
            entry = i
        elif entry is not None:
            break
    out: dict[str, float | None] = {f'fwd{h}': None for h in horizons}
    if entry is None:
        return out
    base = closes[entry]
    if not base:
        return out
    for h in horizons:
        idx = entry + h
        if idx < len(closes):
            out[f'fwd{h}'] = round((closes[idx] / base - 1.0) * 100, 4)
    return out


def _avg(vals: list[float | None]) -> float | None:
    nums = [v for v in vals if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _hit_rate(flags: list[bool | None]) -> float | None:
    known = [1 if flag else 0 for flag in flags if flag is not None]
    if not known:
        return None
    return round(sum(known) / len(known), 4)


def _quote_from_mysql(q: dict[str, Any]) -> dict[str, Any]:
    return {
        'last': q.get('price'),
        'changeRate': q.get('changeRate'),
        'tradeDate': q.get('tradeDate'),
    }


class MarketWatchlistService:
    """行情自选清单服务。"""

    @classmethod
    async def get_list_services(
        cls,
        query_db: AsyncSession,
        query_object: MarketWatchlistPageQueryModel,
        is_page: bool = True,
        user_id: int | None = None,
    ) -> PageModel | list[dict[str, Any]]:
        if not user_id:
            raise ServiceException(message='无法识别当前用户')
        query_object.user_id = user_id
        result = await MarketWatchlistDao.get_watchlist(query_db, query_object, is_page)
        if isinstance(result, PageModel):
            result.rows = [_serialize_market_watchlist_row(row) for row in (result.rows or [])]
            return result
        return [_serialize_market_watchlist_row(row) for row in (result or [])]

    @classmethod
    async def add_services(
        cls, query_db: AsyncSession, add_model: AddMarketWatchlistModel, user_id: int
    ) -> CrudResponseModel:
        symbol = (add_model.symbol or '').strip().upper()
        market = (add_model.market or 'US').strip().upper()
        if not symbol:
            raise ServiceException(message='标的代码不能为空')
        if not user_id:
            raise ServiceException(message='无法识别当前用户')
        existing = await MarketWatchlistDao.get_by_symbol(query_db, symbol, market, user_id=user_id)
        if existing:
            return CrudResponseModel(is_success=True, message=f'{symbol}({market}) 已在自选中')
        name = None
        inst = await MarketInstrumentDao.get_by_symbol(query_db, symbol)
        if inst:
            name = inst.name
            market = (inst.market or market).upper()
        else:
            meta = get_instrument_meta(symbol)
            if meta:
                name = meta[1]
        now = datetime.now()
        try:
            await MarketWatchlistDao.add(
                query_db,
                {
                    'user_id': user_id,
                    'symbol': symbol,
                    'market': market,
                    'name': name,
                    'note': add_model.note,
                    'enabled': '1',
                    'sort_order': 0,
                    'create_time': now,
                    'update_time': now,
                },
            )
            await query_db.commit()
            await _overview_cache_clear(user_id)
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def delete_services(cls, query_db: AsyncSession, ids: str, user_id: int) -> CrudResponseModel:
        if not user_id:
            raise ServiceException(message='无法识别当前用户')
        if not ids:
            raise ServiceException(message='传入ID为空')
        try:
            id_list = [int(i) for i in ids.split(',') if i.strip()]
        except ValueError:
            raise ServiceException(message='ID格式非法，应为逗号分隔的数字') from None
        try:
            await MarketWatchlistDao.delete_by_ids(query_db, id_list, user_id=user_id)
            await query_db.commit()
            await _overview_cache_clear(user_id)
            return CrudResponseModel(is_success=True, message='删除成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    def serialize_analysis(cls, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            'analysisId': row.analysis_id,
            'symbol': row.symbol,
            'market': row.market,
            'price': row.price,
            'changePercent': row.change_percent,
            'stance': row.stance,
            'recommendation': row.recommendation,
            'confidence': row.confidence,
            'summary': row.summary,
            'indicatorReview': row.indicator_review,
            'newsReview': row.news_review,
            'sentimentReview': row.sentiment_review,
            'operationAdvice': row.operation_advice,
            'riskWarning': row.risk_warning,
            'source': row.source,
            'modelName': row.model_name,
            'analysisTime': _fmt_dt(row.analysis_time),
        }

    @classmethod
    async def overview_services(cls, query_db: AsyncSession, user_id: int) -> dict[str, Any]:
        if not user_id:
            raise ServiceException(message='无法识别当前用户')
        cached = await _overview_cache_get(user_id)
        if cached is not None:
            return cached
        payload = await cls._build_overview(query_db, user_id)
        await _overview_cache_set(user_id, payload)
        return payload

    @classmethod
    async def _build_overview(cls, query_db: AsyncSession, user_id: int) -> dict[str, Any]:  # noqa: PLR0912
        items = await MarketWatchlistDao.get_enabled(query_db, user_id=user_id)
        pairs = [(r.symbol, r.market or 'US') for r in items]
        latest_map = await MarketWatchlistAnalysisDao.list_latest_by_symbols(query_db, pairs, user_id=user_id)
        all_symbols = [row.symbol for row in items]
        mysql_quotes = await MarketInstrumentDao.get_latest_daily_quotes(query_db, all_symbols)
        quotes: dict[str, dict[str, Any]] = {}
        for symbol, raw in mysql_quotes.items():
            if raw.get('price') is not None:
                quotes[symbol] = _quote_from_mysql(raw)
        by_market: dict[str, list[str]] = {}
        for row in items:
            if row.symbol not in quotes or quotes[row.symbol].get('last') is None:
                by_market.setdefault((row.market or 'US').upper(), []).append(row.symbol)
        influx_hits = 0

        async def _influx_market(market: str, symbols: list[str]) -> dict[str, list]:
            try:
                return await asyncio.to_thread(InfluxUtil.query_latest_klines, market, symbols, 2, '-60d') or {}
            except Exception as exc:
                logger.error(f'[自选] 行情批量查询失败 market={market}: {exc}')
                return {}

        influx_jobs = [
            _influx_market(market, symbols) for market, symbols in by_market.items() if symbols
        ]
        influx_groups = await asyncio.gather(*influx_jobs) if influx_jobs else []
        missing = [symbols for symbols in by_market.values() if symbols]
        for symbols, grouped in zip(missing, influx_groups, strict=False):
            for symbol in symbols:
                quote = MarketService._build_quote_from_klines(grouped.get(symbol) or [])
                if quote:
                    quotes[symbol] = quote
                    influx_hits += 1
        if influx_hits and mysql_quotes:
            quote_source = 'mysql+influx'
        elif influx_hits:
            quote_source = 'influx'
        else:
            quote_source = 'mysql'

        rows = []
        stance_count = {'偏多': 0, '偏空': 0, '中性': 0}
        last_time = None
        for row in items:
            key = (row.symbol.upper(), (row.market or 'US').upper())
            analysis = cls.serialize_analysis(latest_map.get(key))
            quote = quotes.get(row.symbol) or {}
            if analysis and analysis.get('stance') in stance_count:
                stance_count[analysis['stance']] += 1
            if analysis and analysis.get('analysisTime'):
                candidates = [x for x in (last_time, analysis['analysisTime']) if x]
                last_time = max(candidates) if candidates else last_time
            groups = parse_note_groups(row.note)
            rows.append(
                {
                    'id': row.id,
                    'userId': row.user_id,
                    'symbol': row.symbol,
                    'market': row.market,
                    'name': _resolve_watchlist_name(row.symbol, row.market or 'US', getattr(row, 'name', None)),
                    'note': row.note,
                    'groups': groups,
                    'enabled': row.enabled,
                    'sortOrder': getattr(row, 'sort_order', 0) or 0,
                    'createTime': _fmt_dt(row.create_time),
                    'last': quote.get('last'),
                    'changeRate': quote.get('changeRate'),
                    'tradeDate': quote.get('tradeDate'),
                    'quoteSource': quote_source,
                    'analysis': analysis,
                    'recommendation': (analysis or {}).get('recommendation'),
                    'stance': (analysis or {}).get('stance'),
                    'confidence': (analysis or {}).get('confidence'),
                    'summary': (analysis or {}).get('summary'),
                    'analysisTime': (analysis or {}).get('analysisTime'),
                    'source': (analysis or {}).get('source'),
                }
            )
        group_counts: dict[str, int] = {}
        for row in rows:
            for name in row.get('groups') or []:
                group_counts[name] = group_counts.get(name, 0) + 1
        groups = [{'name': name, 'count': count} for name, count in sorted(group_counts.items(), key=lambda x: (-x[1], x[0]))]
        # 打开终端不解密模型密钥；AI 是否可用由分析记录本身表达。
        ai_conf = {'available': True, 'modelName': None}
        payload = {
            'count': len(rows),
            'bullish': stance_count['偏多'],
            'bearish': stance_count['偏空'],
            'neutral': stance_count['中性'],
            'lastAnalysisTime': last_time,
            'quoteSource': quote_source,
            'aiAvailable': bool(ai_conf.get('available')),
            'aiModel': ai_conf.get('modelName'),
            'aiHint': None
            if ai_conf.get('available')
            else '未配置可用 AI 模型，分析将使用规则打分兜底。请在「AI 模型管理」适用范围选行情中心，默认 grok-4.6。',
            'groups': groups,
            'items': rows,
        }
        return payload

    @classmethod
    async def history_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        limit: int = 24,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        symbol = (symbol or '').strip().upper()
        rows = await MarketWatchlistAnalysisDao.list_history(
            query_db, symbol, market, limit=limit, user_id=user_id
        )
        items = [cls.serialize_analysis(r) for r in rows]
        series = [
            {
                'time': it.get('analysisTime'),
                'confidence': it.get('confidence'),
                'recommendation': it.get('recommendation'),
                'stance': it.get('stance'),
                'price': it.get('price'),
            }
            for it in items
            if it
        ]
        series.reverse()
        return {
            'symbol': symbol,
            'market': (market or 'US').upper(),
            'items': items,
            'series': series,
            'count': len(rows),
        }

    @classmethod
    async def analyze_one(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        name: str | None = None,
        watchlist_id: int | None = None,
        user_id: int | None = None,
        refresh_content: bool = False,
        ai_conf: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del ai_conf  # 统一走 StockPickService 内部解析行情中心 Grok 4.6
        del refresh_content
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        resolved_name = name or _resolve_watchlist_name(symbol, market)
        analyzed = await StockPickService.analyze_symbol(
            query_db,
            symbol,
            market,
            use_ai=True,
            name=resolved_name,
        )
        if not analyzed.get('ok'):
            return {
                'ok': False,
                'symbol': symbol,
                'market': market,
                'message': analyzed.get('message') or '分析失败',
            }

        source = analyzed.get('source') or 'rule'
        model_name = analyzed.get('modelName')
        message = analyzed.get('message') or '分析成功'
        row = await MarketWatchlistAnalysisDao.add(
            query_db,
            {
                'watchlist_id': watchlist_id,
                'user_id': user_id,
                'symbol': symbol,
                'market': market,
                'price': analyzed.get('price'),
                'change_percent': analyzed.get('changePct'),
                'stance': analyzed.get('stance'),
                'recommendation': analyzed.get('recommendation'),
                'confidence': analyzed.get('confidence'),
                'summary': analyzed.get('summary'),
                'indicator_review': analyzed.get('indicatorReview'),
                'news_review': '',
                'sentiment_review': analyzed.get('sentimentReview'),
                'operation_advice': analyzed.get('operationAdvice'),
                'risk_warning': analyzed.get('riskWarning'),
                'source': source,
                'model_name': model_name,
                'indicators_json': _dump(analyzed.get('metrics') or {}),
                'news_json': _dump([]),
                'sentiment_json': _dump({'summary': analyzed.get('sentimentReview')}),
                'raw_json': _dump(
                    {
                        'recommendation': analyzed.get('recommendation'),
                        'stance': analyzed.get('stance'),
                        'confidence': analyzed.get('confidence'),
                        'summary': analyzed.get('summary'),
                        'indicatorReview': analyzed.get('indicatorReview'),
                        'sentimentReview': analyzed.get('sentimentReview'),
                        'operationAdvice': analyzed.get('operationAdvice'),
                        'riskWarning': analyzed.get('riskWarning'),
                        'pickScore': analyzed.get('pickScore'),
                        'factorScore': analyzed.get('factorScore'),
                        'signal': analyzed.get('signal'),
                        'source': source,
                    }
                ),
                'analysis_time': datetime.now(),
            },
        )
        payload = cls.serialize_analysis(row) or {}
        rec = payload.get('recommendation')
        if rec in REC_SIGN:
            try:
                from module_trade.dao.trade_dao import TradeDao  # noqa: PLC0415 - 避免跨模块循环导入

                await TradeDao.add_notification(
                    query_db,
                    {
                        'title': f'自选建议 {symbol} {rec}',
                        'content': (
                            f'{symbol} {payload.get("stance") or ""} · '
                            f'置信度 {payload.get("confidence") if payload.get("confidence") is not None else "--"} · '
                            f'{(payload.get("summary") or "")[:180]}'
                        ),
                        'level': 'warning' if rec in {'减仓', '卖出'} else 'success',
                        'category': 'watchlist',
                    },
                )
            except Exception as exc:
                logger.info(f'[自选分析] 写通知跳过: {exc}')
        await query_db.commit()
        payload.update(
            {
                'ok': True,
                'message': message,
                'name': resolved_name,
                'pickScore': analyzed.get('pickScore'),
                'factorScore': analyzed.get('factorScore'),
                'signal': analyzed.get('signal'),
                'klineCount': analyzed.get('klineCount'),
            }
        )
        return payload

    @classmethod
    async def analyze_services(
        cls,
        query_db: AsyncSession,
        body: MarketWatchlistAnalyzeModel,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        targets: list[dict[str, Any]] = []
        if body.symbol:
            symbol = body.symbol.strip().upper()
            market = (body.market or 'US').strip().upper()
            item = (
                await MarketWatchlistDao.get_by_symbol(query_db, symbol, market, user_id=user_id)
                if user_id
                else None
            )
            targets.append(
                {
                    'id': item.id if item else None,
                    'userId': user_id,
                    'symbol': symbol,
                    'market': market,
                    'name': _resolve_watchlist_name(
                        symbol, market, getattr(item, 'name', None) if item else None
                    ),
                }
            )
        else:
            if not user_id:
                raise ServiceException(message='无法识别当前用户')
            enabled = await MarketWatchlistDao.get_enabled(query_db, user_id=user_id)
            if not enabled:
                raise ServiceException(message='自选清单为空，请先添加关注标的')
            targets.extend(
                {
                    'id': row.id,
                    'userId': row.user_id,
                    'symbol': row.symbol,
                    'market': row.market,
                    'name': _resolve_watchlist_name(row.symbol, row.market or 'US', getattr(row, 'name', None)),
                }
                for row in enabled[:MAX_WATCHLIST_BATCH]
            )

        results: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        async def _analyze_target(target: dict[str, Any]) -> dict[str, Any]:
            return await cls.analyze_one(
                query_db,
                symbol=target['symbol'],
                market=target['market'] or 'US',
                name=target.get('name'),
                watchlist_id=target.get('id'),
                user_id=target.get('userId') or user_id,
                refresh_content=bool(body.refresh_content),
            )

        # 并发执行但限流，避免同时打满 Influx/LLM；AsyncSession 非并发安全，
        # 因此共享会话的操作仍由 analyze_one 内部顺序使用，这里只并行 IO 密集部分
        semaphore = asyncio.Semaphore(3)

        async def _bounded(t: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await _analyze_target(t)

        outcomes = await asyncio.gather(*( _bounded(t) for t in targets ), return_exceptions=True)
        for target, outcome in zip(targets, outcomes, strict=False):
            if isinstance(outcome, BaseException):
                logger.warning(f'[自选分析] {target.get("symbol")} 失败: {outcome}')
                failed.append({'symbol': target.get('symbol'), 'reason': str(outcome)})
                try:
                    await query_db.rollback()
                except Exception:
                    pass
            else:
                results.append(outcome)
        try:
            await MarketWatchlistAnalysisDao.prune_older_than(query_db, datetime.now() - timedelta(days=7))
            await query_db.commit()
        except Exception:
            await query_db.rollback()
        await _overview_cache_clear(user_id)
        return {
            'ok': len(failed) == 0,
            'count': len(results),
            'failedCount': len(failed),
            'aiAvailable': True,
            'items': results,
            'failed': failed,
            'message': f'完成 {len(results)} 只，失败 {len(failed)} 只',
        }

    @classmethod
    async def backtest_services(
        cls, query_db: AsyncSession, user_id: int, limit: int = 200
    ) -> dict[str, Any]:
        rows = await MarketWatchlistAnalysisDao.list_recent_by_user(query_db, user_id, limit=limit)
        kline_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        items: list[dict[str, Any]] = []
        for row in rows:
            rec = row.recommendation or ''
            sign = REC_SIGN.get(rec)
            if not sign:
                continue
            symbol = row.symbol
            market = (row.market or 'US').upper()
            as_of = _fmt_dt(row.analysis_time) or ''
            cache_key = (symbol, market)
            if cache_key not in kline_cache:
                kline_cache[cache_key] = await asyncio.to_thread(
                    InfluxUtil.query_klines, market, symbol, '-400d', 'now()', 400
                )
            fwds = forward_returns_from_klines(kline_cache[cache_key], as_of)
            fwd1 = fwds.get('fwd1')
            fwd5 = fwds.get('fwd5')
            signed1 = None if fwd1 is None else round(fwd1 * sign, 4)
            signed5 = None if fwd5 is None else round(fwd5 * sign, 4)
            items.append(
                {
                    'analysisId': row.analysis_id,
                    'symbol': symbol,
                    'market': market,
                    'recommendation': rec,
                    'stance': row.stance,
                    'confidence': row.confidence,
                    'analysisTime': as_of,
                    'price': row.price,
                    'fwd1': fwd1,
                    'fwd5': fwd5,
                    'signed1': signed1,
                    'signed5': signed5,
                    'hit1': None if signed1 is None else signed1 > 0,
                    'hit5': None if signed5 is None else signed5 > 0,
                }
            )
        pending = sum(1 for it in items if it['fwd1'] is None)
        return {
            'count': len(items),
            'pendingCount': pending,
            'scoredCount': len(items) - pending,
            'avgFwd1': _avg([it['fwd1'] for it in items]),
            'avgFwd5': _avg([it['fwd5'] for it in items]),
            'avgSigned1': _avg([it['signed1'] for it in items]),
            'avgSigned5': _avg([it['signed5'] for it in items]),
            'hitRate1': _hit_rate([it['hit1'] for it in items]),
            'hitRate5': _hit_rate([it['hit5'] for it in items]),
            'items': items[:80],
            'message': '买入/加仓视为多，减仓/卖出视为空；收益为建议日后 1/5 个交易日涨跌幅。持有与观望不计入。',
        }

    @classmethod
    async def run_hourly_job(cls, query_db: AsyncSession) -> dict[str, Any]:
        from utils.longbridge_breaker import LongbridgeBreaker  # noqa: PLC0415 - 按需加载熔断器

        if not LongbridgeBreaker.allow():
            return {
                'ok': True,
                'count': 0,
                'failedCount': 0,
                'skipped': True,
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
            }
        enabled = await MarketWatchlistDao.get_all_enabled(query_db)
        if not enabled:
            return {'ok': True, 'count': 0, 'failedCount': 0, 'skipped': True, 'message': '自选清单为空，跳过'}
        user_ids = sorted({int(row.user_id or 1) for row in enabled})
        total = {'ok': True, 'count': 0, 'failedCount': 0, 'users': len(user_ids), 'items': [], 'failed': []}
        for uid in user_ids:
            part = await cls.analyze_services(
                query_db, MarketWatchlistAnalyzeModel(symbol=None, refresh_content=True), user_id=uid
            )
            total['count'] += int(part.get('count') or 0)
            total['failedCount'] += int(part.get('failedCount') or 0)
            total['ok'] = bool(total['ok'] and part.get('ok'))
            total['items'].extend(part.get('items') or [])
            total['failed'].extend(part.get('failed') or [])
        total['message'] = f'完成 {total["count"]} 只，失败 {total["failedCount"]} 只，覆盖 {len(user_ids)} 个用户'
        return total
