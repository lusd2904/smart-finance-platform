"""
行情中心自选清单：CRUD + 小时级综合分析（指标 / 长桥资讯 / 舆情）。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import CrudResponseModel, PageModel
from exceptions.exception import ServiceException
from module_ai.dao.ai_model_dao import AiModelDao
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
from module_market.service.content_cache_service import SymbolContentService
from module_market.service.indicator_service import IndicatorService
from module_market.service.market_service import MarketService
from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer, rule_based_analysis
from module_sentiment.dao.sentiment_dao import SentimentAnalysisDao, SentimentNewsDao
from utils.crypto_util import CryptoUtil
from utils.influx_util import InfluxUtil
from utils.log_util import logger

MAX_WATCHLIST_BATCH = 30


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
        query_object.user_id = user_id
        return await MarketWatchlistDao.get_watchlist(query_db, query_object, is_page)

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
            raise ServiceException(message=f'{symbol}({market}) 已在自选清单中')
        name = None
        inst = await MarketInstrumentDao.get_by_symbol(query_db, symbol)
        if inst:
            name = inst.name
            market = (inst.market or market).upper()
        else:
            meta = get_instrument_meta(symbol)
            if meta:
                name = meta[1]
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
                    'create_time': datetime.now(),
                    'update_time': datetime.now(),
                },
            )
            await query_db.commit()
            return CrudResponseModel(is_success=True, message='新增成功')
        except Exception:
            await query_db.rollback()
            raise

    @classmethod
    async def delete_services(cls, query_db: AsyncSession, ids: str, user_id: int) -> CrudResponseModel:
        if not ids:
            raise ServiceException(message='传入ID为空')
        try:
            id_list = [int(i) for i in ids.split(',') if i.strip()]
        except ValueError:
            raise ServiceException(message='ID格式非法，应为逗号分隔的数字') from None
        try:
            await MarketWatchlistDao.delete_by_ids(query_db, id_list, user_id=user_id)
            await query_db.commit()
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
        items = await MarketWatchlistDao.get_enabled(query_db, user_id=user_id)
        pairs = [(r.symbol, r.market or 'US') for r in items]
        latest_map = await MarketWatchlistAnalysisDao.list_latest_by_symbols(query_db, pairs, user_id=user_id)
        quotes: dict[str, dict[str, Any]] = {}
        by_market: dict[str, list[str]] = {}
        for row in items:
            by_market.setdefault((row.market or 'US').upper(), []).append(row.symbol)
        for market, symbols in by_market.items():
            grouped = await asyncio.to_thread(InfluxUtil.query_latest_klines, market, symbols, 2, '-60d')
            for symbol in symbols:
                quote = MarketService._build_quote_from_klines(grouped.get(symbol) or [])
                if quote:
                    quotes[symbol] = quote
        # Browse/list path: last price from Influx latest 2 daily bars only — do not overlay Longbridge realtime.
        quote_source = 'influx'

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
            rows.append(
                {
                    'id': row.id,
                    'symbol': row.symbol,
                    'market': row.market,
                    'name': row.name,
                    'note': row.note,
                    'enabled': row.enabled,
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
        ai_conf = await cls._resolve_ai(query_db)
        return {
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
            else '未配置可用 AI 模型，小时分析将使用技术指标兜底。请在「AI 模型管理」填写 Base URL / API Key / 模型。',
            'items': rows,
        }

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
    async def _resolve_ai(cls, query_db: AsyncSession) -> dict[str, Any]:
        base_url = api_key = model_name = None
        temperature = 0.2
        try:
            ai_model = await AiModelDao.resolve_ai_model_for_business(query_db, 'market')
            if ai_model:
                base_url = ai_model.base_url
                api_key = CryptoUtil.decrypt(ai_model.api_key) if ai_model.api_key else None
                model_name = ai_model.model_code
                if ai_model.temperature is not None:
                    temperature = ai_model.temperature
        except Exception as exc:
            logger.warning(f'[自选分析] 解析 AI 模型失败: {exc}')
        return {
            'baseUrl': base_url,
            'apiKey': api_key,
            'modelName': model_name,
            'temperature': temperature,
            'available': bool(base_url and api_key and model_name),
        }

    @classmethod
    async def _collect_context(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str,
        name: str | None,
        refresh_content: bool,
    ) -> dict[str, Any]:
        klines = await asyncio.to_thread(InfluxUtil.query_klines, market, symbol, '-180d', 'now()', 200)
        quote = MarketService._build_quote_from_klines(klines[-2:] if klines else [])
        snapshot = await asyncio.to_thread(IndicatorService.latest_snapshot, klines) if klines else {}
        news_items: list[dict[str, Any]] = []
        for content_type in ('news', 'announcement', 'topic'):
            try:
                bundle = await SymbolContentService.get_content(
                    query_db,
                    symbol=symbol,
                    market=market,
                    content_type=content_type,
                    limit=6,
                    refresh=refresh_content and content_type == 'news',
                )
                for item in bundle.get('items') or []:
                    news_items.append(
                        {
                            'contentType': content_type,
                            'title': item.get('title'),
                            'summary': (item.get('summary') or item.get('content') or '')[:400],
                            'publishedAt': item.get('publishedAt'),
                            'sourceName': item.get('sourceName'),
                        }
                    )
            except Exception as exc:
                logger.warning(f'[自选分析] 读取 {symbol} {content_type} 失败: {exc}')

        keywords = [symbol]
        if name:
            keywords.append(name)
            compact = name.replace('-W', '').replace('-SW', '').strip()
            if compact and compact != name:
                keywords.append(compact)
        sentiment_rows = await SentimentNewsDao.search_news_by_keywords(query_db, keywords, limit=8)
        sentiment_news = [
            {
                'title': r.title,
                'content': (r.content or '')[:400],
                'source': r.source,
                'pubTime': _fmt_dt(r.pub_time),
            }
            for r in sentiment_rows
        ]
        latest_sent = await SentimentAnalysisDao.get_latest_analysis(query_db)
        market_sentiment = None
        if latest_sent:
            market_sentiment = {
                'summary': latest_sent.summary,
                'usDirection': latest_sent.us_direction,
                'usScore': latest_sent.us_score,
                'hkDirection': latest_sent.hk_direction,
                'hkScore': latest_sent.hk_score,
                'aDirection': latest_sent.a_direction,
                'aScore': latest_sent.a_score,
                'riskEvents': latest_sent.risk_events,
            }
        return {
            'symbol': symbol,
            'market': market,
            'name': name or symbol,
            'price': quote.get('last') or snapshot.get('close'),
            'changePercent': quote.get('changeRate'),
            'indicators': snapshot,
            'news': news_items[:12],
            'sentimentNews': sentiment_news,
            'marketSentiment': market_sentiment,
            'klineCount': len(klines or []),
        }

    @classmethod
    def _normalize_result(cls, parsed: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
        data = dict(fallback)
        if not parsed:
            return data
        mapping = {
            'stance': 'stance',
            'recommendation': 'recommendation',
            'confidence': 'confidence',
            'summary': 'summary',
            'indicator_review': 'indicator_review',
            'news_review': 'news_review',
            'sentiment_review': 'sentiment_review',
            'operation_advice': 'operation_advice',
            'risk_warning': 'risk_warning',
            'key_points': 'key_points',
        }
        for src, dest in mapping.items():
            if parsed.get(src) not in (None, ''):
                data[dest] = parsed.get(src)
        try:
            data['confidence'] = int(data.get('confidence') or 50)
        except (TypeError, ValueError):
            data['confidence'] = 50
        data['confidence'] = max(0, min(100, data['confidence']))
        rec = str(data.get('recommendation') or '观望')
        if rec.lower() in {'buy', 'long'}:
            rec = '买入'
        elif rec.lower() in {'sell', 'short'}:
            rec = '卖出'
        elif rec.lower() in {'hold'}:
            rec = '持有'
        data['recommendation'] = rec
        return data

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
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        context = await cls._collect_context(query_db, symbol, market, name, refresh_content)
        fallback = rule_based_analysis(context)
        ai_conf = ai_conf if ai_conf is not None else await cls._resolve_ai(query_db)
        parsed = None
        source = 'rule'
        raw = ''
        model_name = None
        message = '已用技术指标生成兜底建议'
        if ai_conf.get('available'):
            ai_result = await WatchlistAiAnalyzer.analyze(
                base_url=ai_conf['baseUrl'],
                api_key=ai_conf['apiKey'],
                model_name=ai_conf['modelName'],
                context=context,
                temperature=float(ai_conf.get('temperature') or 0.2),
            )
            raw = ai_result.get('raw') or ''
            if ai_result.get('ok'):
                parsed = ai_result.get('result')
                source = 'ai'
                model_name = ai_conf.get('modelName')
                message = '分析成功'
            else:
                message = f'模型失败，已回退指标建议: {ai_result.get("error")}'
        else:
            message = '未配置 AI，已用技术指标、资讯与舆情生成兜底建议'

        result = cls._normalize_result(parsed, fallback)
        row = await MarketWatchlistAnalysisDao.add(
            query_db,
            {
                'watchlist_id': watchlist_id,
                'user_id': user_id,
                'symbol': symbol,
                'market': market,
                'price': context.get('price'),
                'change_percent': context.get('changePercent'),
                'stance': result.get('stance'),
                'recommendation': result.get('recommendation'),
                'confidence': result.get('confidence'),
                'summary': result.get('summary'),
                'indicator_review': result.get('indicator_review'),
                'news_review': result.get('news_review'),
                'sentiment_review': result.get('sentiment_review'),
                'operation_advice': result.get('operation_advice'),
                'risk_warning': result.get('risk_warning'),
                'source': source,
                'model_name': model_name,
                'indicators_json': _dump(context.get('indicators') or {}),
                'news_json': _dump(context.get('news') or []),
                'sentiment_json': _dump(
                    {
                        'news': context.get('sentimentNews') or [],
                        'market': context.get('marketSentiment'),
                    }
                ),
                'raw_json': _dump(parsed or {'fallback': fallback, 'raw': raw[:4000]}),
                'analysis_time': datetime.now(),
            },
        )
        payload = cls.serialize_analysis(row) or {}
        rec = payload.get('recommendation')
        if rec in REC_SIGN:
            try:
                from module_trade.dao.trade_dao import TradeDao

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
                'name': context.get('name'),
                'newsCount': len(context.get('news') or []),
                'sentimentCount': len(context.get('sentimentNews') or []),
                'klineCount': context.get('klineCount'),
                'keyPoints': result.get('key_points') or [],
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
        ai_conf = await cls._resolve_ai(query_db)
        targets: list[dict[str, Any]] = []
        if body.symbol:
            symbol = body.symbol.strip().upper()
            market = (body.market or 'US').strip().upper()
            item = await MarketWatchlistDao.get_by_symbol(query_db, symbol, market, user_id=user_id)
            meta = get_instrument_meta(symbol)
            targets.append(
                {
                    'id': item.id if item else None,
                    'userId': (item.user_id if item else None) or user_id,
                    'symbol': symbol,
                    'market': market,
                    'name': (item.name if item else None) or (meta[1] if meta else symbol),
                }
            )
        else:
            enabled = await MarketWatchlistDao.get_enabled(query_db, user_id=user_id)
            if not enabled:
                raise ServiceException(message='自选清单为空，请先添加关注标的')
            for row in enabled[:MAX_WATCHLIST_BATCH]:
                targets.append(
                    {
                        'id': row.id,
                        'userId': row.user_id,
                        'symbol': row.symbol,
                        'market': row.market,
                        'name': row.name,
                    }
                )

        results = []
        failed = []
        for target in targets:
            try:
                results.append(
                    await cls.analyze_one(
                        query_db,
                        symbol=target['symbol'],
                        market=target['market'] or 'US',
                        name=target.get('name'),
                        watchlist_id=target.get('id'),
                        user_id=target.get('userId') or user_id,
                        refresh_content=bool(body.refresh_content),
                        ai_conf=ai_conf,
                    )
                )
            except Exception as exc:
                logger.warning(f'[自选分析] {target.get("symbol")} 失败: {exc}')
                failed.append({'symbol': target.get('symbol'), 'reason': str(exc)})
                try:
                    await query_db.rollback()
                except Exception:
                    pass
        try:
            await MarketWatchlistAnalysisDao.prune_older_than(query_db, datetime.now() - timedelta(days=7))
            await query_db.commit()
        except Exception:
            await query_db.rollback()
        return {
            'ok': len(failed) == 0,
            'count': len(results),
            'failedCount': len(failed),
            'aiAvailable': bool(ai_conf.get('available')),
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
        enabled = await MarketWatchlistDao.get_enabled(query_db, user_id=None)
        if not enabled:
            return {'ok': True, 'count': 0, 'failedCount': 0, 'skipped': True, 'message': '自选清单为空，跳过'}
        return await cls.analyze_services(
            query_db, MarketWatchlistAnalyzeModel(symbol=None, refresh_content=True), user_id=None
        )
