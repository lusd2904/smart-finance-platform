"""全市场智能选股：指标 + 舆情 + 开盘指数（休市去掉指数）。"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select

from module_ai.constant.ai_model_resolve import GROK46_MODEL_CODES, MARKET_SCOPE
from module_ai.dao.ai_model_dao import AiModelDao
from module_market.constant.instruments import TARGET_INSTRUMENTS, get_instrument_meta
from module_market.dao.heat_dao import MarketHeatDao
from module_market.dao.market_dao import MarketWatchlistDao
from module_market.dao.stock_pick_dao import StockPickDao
from module_market.service.heat_service import MarketHeatService
from module_market.service.index_quotes_service import MarketIndexService, list_session_status
from module_market.service.stock_pick_analyzer import StockPickAnalyzer
from utils.time_format_util import now_beijing
from module_market.service.stock_pick_scoring import (
    AI_CONCURRENCY,
    CANDIDATE_CAP,
    PICKS_PER_MARKET,
    SENTIMENT_FIELD,
    apply_ai_result,
    combine_pick_score,
    merge_candidates,
    reco_from_signal,
    select_top_picks,
)
from module_quant.service.factor_service import FactorService
from module_quant.service.strategy_service import decide_signal
from module_sentiment.dao.sentiment_dao import SentimentAnalysisDao
from module_sentiment.entity.do.sentiment_do import SentimentNews
from module_sentiment.entity.vo.sentiment_vo import normalize_sentiment_score
from utils.crypto_util import CryptoUtil
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MARKETS = ('CN', 'HK', 'US')
MOOD_CACHE_KEY = 'market:stock-pick:mood:v1'
MOOD_CACHE_TTL = 30
INDEX_QUOTES_TIMEOUT_S = 5.0


def _featured_for_market(market: str) -> list[dict[str, Any]]:
    return [
        {'symbol': symbol, 'name': name, 'market': mkt, 'category': category}
        for symbol, name, mkt, category in TARGET_INSTRUMENTS
        if mkt == market
    ]


class StockPickService:
    @classmethod
    def _serialize_sentiment(cls, row: Any) -> dict[str, Any]:
        if not row:
            return {}
        return {
            'summary': row.summary,
            'usScore': normalize_sentiment_score(row.us_score),
            'hkScore': normalize_sentiment_score(row.hk_score),
            'aScore': normalize_sentiment_score(row.a_score),
            'usDirection': row.us_direction,
            'hkDirection': row.hk_direction,
            'aDirection': row.a_direction,
            'usReason': row.us_reason,
            'hkReason': row.hk_reason,
            'aReason': row.a_reason,
            'analyzedAt': row.create_time.strftime('%Y-%m-%d %H:%M:%S') if row.create_time else None,
            'modelName': row.model_name,
        }

    @classmethod
    async def _headlines(cls, db: AsyncSession, limit: int = 8) -> list[dict[str, str]]:
        rows = (
            (await db.execute(select(SentimentNews).order_by(desc(SentimentNews.pub_time)).limit(limit)))
            .scalars()
            .all()
        )
        return [
            {
                'title': row.title,
                'source': row.source or '',
                'pubTime': row.pub_time.strftime('%Y-%m-%d %H:%M') if row.pub_time else '',
            }
            for row in rows
        ]

    @classmethod
    async def _resolve_default_trade_date(cls, db: AsyncSession) -> str | None:
        dates: list[str] = []
        for market in MARKETS:
            heat = await MarketHeatDao.get_latest_heat(db, market)
            if heat and heat.trade_date:
                dates.append(str(heat.trade_date)[:10])
        heat_dates = await MarketHeatDao.list_distinct_trade_dates(db, limit=1)
        if heat_dates:
            dates.append(heat_dates[0])
        latest_pick = await StockPickDao.get_latest(db)
        if latest_pick and latest_pick.trade_date:
            dates.append(str(latest_pick.trade_date)[:10])
        return max(dates) if dates else None

    @classmethod
    async def get_mood_services(cls, db: AsyncSession) -> dict[str, Any]:
        cached = await cache_get_json(MOOD_CACHE_KEY)
        if isinstance(cached, dict):
            return {**cached, 'cached': True}

        sessions = list_session_status()
        try:
            quotes = await asyncio.wait_for(
                MarketIndexService.get_in_session_quotes(),
                timeout=INDEX_QUOTES_TIMEOUT_S,
            )
        except (TimeoutError, asyncio.TimeoutError, Exception) as exc:
            logger.warning(f'[stock-pick-mood] index quotes failed: {exc}')
            quotes = {'items': []}
        latest = await SentimentAnalysisDao.get_latest_analysis(db)
        sentiment = cls._serialize_sentiment(latest)
        heats: dict[str, Any] = {}
        for market in MARKETS:
            heat = await MarketHeatDao.get_latest_heat(db, market)
            if heat:
                heats[market] = MarketHeatService._serialize_heat(heat)
        open_markets = [m for m, info in sessions.items() if info.get('open')]
        payload = {
            'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            'sessions': sessions,
            'openMarkets': open_markets,
            'indices': quotes.get('items') or [],
            'sentiment': sentiment,
            'heat': heats,
            'headlines': await cls._headlines(db),
            'hint': (
                '仅开盘市场附带实时指数；休市市场只用指标和舆情动态分析。'
                if open_markets
                else '三市场均未开盘，已去掉实时指数，按指标+舆情分析。'
            ),
        }
        await cache_set_json(MOOD_CACHE_KEY, payload, MOOD_CACHE_TTL)
        return payload

    @classmethod
    async def list_dates_services(cls, db: AsyncSession, limit: int = 60) -> dict[str, Any]:
        cap = max(1, min(int(limit or 60), 120))
        pick_rows = await StockPickDao.list_dates(db, limit=cap)
        pick_by_date = {str(row.trade_date)[:10]: row for row in pick_rows}
        heat_dates = await MarketHeatDao.list_distinct_trade_dates(db, limit=cap)
        all_dates = sorted(set(pick_by_date) | set(heat_dates), reverse=True)[:cap]
        default_trade_date = max(all_dates) if all_dates else await cls._resolve_default_trade_date(db)
        dates: list[dict[str, Any]] = []
        for trade_day in all_dates:
            row = pick_by_date.get(trade_day)
            if row:
                dates.append(
                    {
                        'id': row.pick_id,
                        'tradeDate': row.trade_date,
                        'status': row.status,
                        'pickedCount': row.picked_count,
                        'aiCount': row.ai_count,
                        'modelName': row.model_name,
                        'updatedAt': row.update_time.strftime('%Y-%m-%d %H:%M:%S') if row.update_time else None,
                        'hasPickSheet': True,
                    }
                )
            else:
                dates.append(
                    {
                        'id': None,
                        'tradeDate': trade_day,
                        'status': 'empty',
                        'pickedCount': 0,
                        'aiCount': 0,
                        'modelName': None,
                        'updatedAt': None,
                        'hasPickSheet': False,
                    }
                )
        return {'dates': dates, 'defaultTradeDate': default_trade_date}

    @classmethod
    async def get_latest_services(
        cls,
        db: AsyncSession,
        market: str | None = None,
        user_id: int | None = None,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        if trade_date:
            target_date = str(trade_date)[:10]
            run = await StockPickDao.get_by_date(db, target_date)
        else:
            target_date = await cls._resolve_default_trade_date(db)
            run = await StockPickDao.get_by_date(db, target_date) if target_date else None
        if not run:
            message = (
                '该交易日暂无选股单'
                if trade_date or target_date
                else '还没有选股单。可手动生成，或等收盘后的定时任务。'
            )
            return {
                'empty': True,
                'message': message,
                'tradeDate': target_date or trade_date,
                'items': [],
            }
        items = await StockPickDao.list_items(db, run.pick_id, market=market)
        watch_set: set[tuple[str, str]] = set()
        if user_id:
            watch = await MarketWatchlistDao.get_enabled(db, user_id=user_id)
            watch_set = {(w.symbol.upper(), (w.market or 'US').upper()) for w in watch}
        payload_items = []
        for row in items:
            tags = []
            try:
                tags = json.loads(row.tags_json or '[]')
            except Exception:
                tags = []
            payload_items.append(
                {
                    'itemId': row.item_id,
                    'rankNo': row.rank_no,
                    'symbol': row.symbol,
                    'name': row.name,
                    'market': row.market,
                    'price': row.price,
                    'changePct': row.change_pct,
                    'factorScore': row.factor_score,
                    'pickScore': row.pick_score,
                    'signal': row.signal,
                    'recommendation': row.recommendation,
                    'stance': row.stance,
                    'confidence': row.confidence,
                    'summary': row.summary,
                    'indicatorReview': row.indicator_review,
                    'sentimentReview': row.sentiment_review,
                    'operationAdvice': row.operation_advice,
                    'riskWarning': row.risk_warning,
                    'tags': tags,
                    'source': row.source,
                    'inWatchlist': (str(row.symbol or '').upper(), str(row.market or 'US').upper()) in watch_set,
                }
            )
        context = {}
        try:
            context = json.loads(run.context_json or '{}')
        except Exception:
            context = {}
        return {
            'empty': False,
            'pickId': run.pick_id,
            'tradeDate': run.trade_date,
            'status': run.status,
            'trigger': run.trigger_source,
            'scannedCount': run.scanned_count,
            'pickedCount': run.picked_count,
            'aiCount': run.ai_count,
            'modelName': run.model_name,
            'openMarkets': [x for x in (run.open_markets or '').split(',') if x],
            'message': run.message,
            'updatedAt': run.update_time.strftime('%Y-%m-%d %H:%M:%S') if run.update_time else None,
            'context': context,
            'items': payload_items,
        }

    @classmethod
    def _build_analyzer_context(cls, mood: dict[str, Any]) -> dict[str, Any]:
        open_markets = set(mood.get('openMarkets') or [])
        sentiment = mood.get('sentiment') or {}
        heats = mood.get('heat') or {}
        index_chg: dict[str, float] = {}
        for item in mood.get('indices') or []:
            market = str(item.get('market') or '').upper()
            chg = item.get('changePct')
            if market and isinstance(chg, (int, float)) and market not in index_chg:
                index_chg[market] = float(chg)
        return {
            'markets': {
                m: {
                    'open': m in open_markets,
                    'heatScore': (heats.get(m) or {}).get('heatScore'),
                    'indexChangePct': index_chg.get(m),
                    'sentiment': sentiment.get(SENTIMENT_FIELD[m]),
                }
                for m in MARKETS
            },
            'sentiment': sentiment,
        }

    @classmethod
    def _score_symbol_row(
        cls,
        *,
        symbol: str,
        name: str,
        market: str,
        klines: list[dict[str, Any]],
        mood: dict[str, Any],
    ) -> dict[str, Any] | None:
        computed = FactorService.compute_from_klines(klines)
        if not computed.get('ok'):
            return None
        open_markets = set(mood.get('openMarkets') or [])
        sentiment = mood.get('sentiment') or {}
        heats = mood.get('heat') or {}
        index_chg: dict[str, float] = {}
        for item in mood.get('indices') or []:
            mkt = str(item.get('market') or '').upper()
            chg = item.get('changePct')
            if mkt and isinstance(chg, (int, float)) and mkt not in index_chg:
                index_chg[mkt] = float(chg)
        metrics = computed.get('metrics') or {}
        score = computed.get('score') or {}
        decision = decide_signal(score)
        heat = heats.get(market) or {}
        sent_raw = sentiment.get(SENTIMENT_FIELD.get(market, 'usScore'))
        opened = market in open_markets
        pick_score = combine_pick_score(
            score.get('total'),
            sentiment_raw=sent_raw,
            heat_score=heat.get('heatScore'),
            index_open=opened,
            index_change_pct=index_chg.get(market),
        )
        reco, stance = reco_from_signal(decision.get('signal'), pick_score)
        tags = list(score.get('tags') or [])[:6]
        tags.append('盘中含指数' if opened else '休市无指数')
        return {
            'symbol': symbol,
            'name': name,
            'market': market,
            'price': metrics.get('latestClose'),
            'changePct': metrics.get('dayChangePercent'),
            'factorScore': score.get('total'),
            'pickScore': pick_score,
            'signal': decision.get('signal'),
            'recommendation': reco,
            'stance': stance,
            'confidence': decision.get('confidence'),
            'reason': decision.get('reason'),
            'summary': decision.get('reason'),
            'indicatorReview': '、'.join(tags) or '指标中性',
            'sentimentReview': sentiment.get('summary') or '暂无舆情',
            'operationAdvice': reco,
            'riskWarning': '无',
            'tags': tags,
            'source': 'rule',
            'metrics': {
                'rsi14': metrics.get('rsi14'),
                'macdHist': metrics.get('macdHist'),
                'ma20': metrics.get('ma20'),
                'volumeRatio20': metrics.get('volumeRatio20'),
                'return20': metrics.get('return20'),
            },
            'klineCount': len(klines),
        }

    @classmethod
    async def analyze_symbol(
        cls,
        db: AsyncSession,
        symbol: str,
        market: str,
        *,
        use_ai: bool = True,
        name: str | None = None,
    ) -> dict[str, Any]:
        """单标的研判：与智能选股同一套指标打分 + 舆情/热度/指数 + Grok 4.6。"""
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        if not symbol:
            return {'ok': False, 'available': False, 'message': '标的代码不能为空', 'symbol': symbol, 'market': market}
        if not name:
            meta = get_instrument_meta(symbol)
            name = meta[1] if meta else symbol

        cutoff = (date.today() - timedelta(days=400)).isoformat()
        kline_map = await StockPickDao.load_recent_daily_klines(db, [symbol], cutoff)
        klines = kline_map.get(symbol) or []
        if not klines:
            return {
                'ok': False,
                'available': True,
                'message': f'标的 {symbol} 暂无K线数据，请先同步',
                'symbol': symbol,
                'market': market,
                'name': name,
            }

        mood = await cls.get_mood_services(db)
        row = cls._score_symbol_row(symbol=symbol, name=name, market=market, klines=klines, mood=mood)
        if not row:
            return {
                'ok': False,
                'available': True,
                'message': f'标的 {symbol} K线不足以计算指标',
                'symbol': symbol,
                'market': market,
                'name': name,
                'klineCount': len(klines),
            }

        ai_cfg = await cls._resolve_ai(db) if use_ai else {'available': False, 'reason': '未启用 AI'}
        model_name = ai_cfg.get('modelName')
        ai_error = ai_cfg.get('reason')
        ai_ok = False
        if ai_cfg.get('available'):
            context = cls._build_analyzer_context(mood)
            ai_result = await StockPickAnalyzer.analyze(
                ai_cfg['baseUrl'],
                ai_cfg['apiKey'],
                ai_cfg['modelName'],
                row,
                context,
                temperature=float(ai_cfg.get('temperature') or 0.2),
            )
            if ai_result.get('ok') and ai_result.get('result'):
                apply_ai_result(row, ai_result['result'])
                ai_ok = True
            else:
                ai_error = str(ai_result.get('error') or ai_error or '模型未返回有效 JSON')
        elif use_ai:
            logger.warning(f'[单标的研判] {symbol} 跳过 AI：{ai_error}')

        message = '分析成功' if (not use_ai or ai_ok or row.get('source') == 'rule') else f'分析失败: {ai_error}'
        return {
            'ok': True,
            'available': bool(ai_cfg.get('available')),
            'symbol': symbol,
            'market': market,
            'name': name,
            'price': row.get('price'),
            'changePct': row.get('changePct'),
            'factorScore': row.get('factorScore'),
            'pickScore': row.get('pickScore'),
            'signal': row.get('signal'),
            'recommendation': row.get('recommendation'),
            'stance': row.get('stance'),
            'confidence': row.get('confidence'),
            'summary': row.get('summary'),
            'indicatorReview': row.get('indicatorReview'),
            'sentimentReview': row.get('sentimentReview'),
            'operationAdvice': row.get('operationAdvice'),
            'riskWarning': row.get('riskWarning'),
            'tags': row.get('tags') or [],
            'source': row.get('source'),
            'modelName': model_name if row.get('source') == 'ai' else None,
            'metrics': row.get('metrics') or {},
            'reason': row.get('reason'),
            'klineCount': row.get('klineCount'),
            'message': message,
            'aiOk': ai_ok,
            'aiError': ai_error if use_ai and not ai_ok else None,
        }

    @classmethod
    async def _resolve_ai(cls, db: AsyncSession) -> dict[str, Any]:
        model = None
        try:
            # 走 AI 模型管理：适用范围「行情中心」优先，没有则默认 Grok 4.6，再回退全局/助手。
            model = await AiModelDao.resolve_ai_model_for_business(
                db, MARKET_SCOPE, preferred_codes=GROK46_MODEL_CODES
            )
        except Exception as exc:
            logger.warning(f'[选股] 解析模型失败: {exc}')
            return {'available': False, 'reason': f'解析模型失败: {exc}'}
        if not model:
            return {'available': False, 'reason': '未配置可用 AI 模型（AI 管理 → 模型管理，适用范围选行情中心，默认 grok-4.6）'}
        api_key = model.api_key
        if api_key:
            try:
                api_key = CryptoUtil.decrypt(api_key)
            except Exception as exc:
                logger.warning(f'[选股] API Key 解密失败: {exc}')
                return {'available': False, 'reason': 'API Key 解密失败'}
        if not (model.base_url and api_key and model.model_code):
            return {'available': False, 'reason': '模型缺少 Base URL / API Key / 模型名'}
        return {
            'available': True,
            'baseUrl': model.base_url,
            'apiKey': api_key,
            'modelName': model.model_code,
            'temperature': model.temperature if model.temperature is not None else 0.2,
        }

    @classmethod
    async def _enrich_picked_with_ai(
        cls,
        picked: list[dict[str, Any]],
        ai_cfg: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[int, str | None]:
        if not picked:
            return 0, None
        sem = asyncio.Semaphore(AI_CONCURRENCY)

        async def _one(row: dict[str, Any]) -> dict[str, Any]:
            async with sem:
                return await StockPickAnalyzer.analyze(
                    ai_cfg['baseUrl'],
                    ai_cfg['apiKey'],
                    ai_cfg['modelName'],
                    row,
                    context,
                    temperature=float(ai_cfg.get('temperature') or 0.2),
                )

        results = await asyncio.gather(*[_one(row) for row in picked], return_exceptions=True)
        ai_count = 0
        last_err: str | None = None
        for row, result in zip(picked, results, strict=False):
            if isinstance(result, Exception):
                last_err = str(result)
                logger.warning(f"[选股AI] {row.get('symbol')} 异常: {result}")
                continue
            if result.get('ok') and result.get('result'):
                apply_ai_result(row, result['result'])
                ai_count += 1
            else:
                last_err = str(result.get('error') or last_err or '模型未返回有效 JSON')
        return ai_count, last_err

    @classmethod
    async def run(cls, db: AsyncSession, *, trigger: str = 'manual', use_ai: bool = True) -> dict[str, Any]:  # noqa: PLR0915
        mood = await cls.get_mood_services(db)
        open_markets = set(mood.get('openMarkets') or [])
        sentiment = mood.get('sentiment') or {}
        heats = mood.get('heat') or {}
        index_chg: dict[str, float] = {}
        for item in mood.get('indices') or []:
            market = str(item.get('market') or '').upper()
            chg = item.get('changePct')
            if market and isinstance(chg, (int, float)) and market not in index_chg:
                index_chg[market] = float(chg)

        trade_dates = [str(h.get('tradeDate')) for h in heats.values() if h.get('tradeDate')]
        trade_date = max(trade_dates) if trade_dates else date.today().isoformat()

        run = await StockPickDao.upsert_run(
            db,
            {
                'trade_date': trade_date,
                'status': 'running',
                'trigger_source': trigger,
                'open_markets': ','.join(sorted(open_markets)),
                'message': '扫描中',
                'context_json': json.dumps(
                    {'mood': {k: mood[k] for k in ('sessions', 'openMarkets', 'indices', 'sentiment', 'hint') if k in mood}},
                    ensure_ascii=False,
                    default=str,
                ),
            },
        )
        pick_id = int(run.pick_id)
        await db.commit()

        scored: list[dict[str, Any]] = []
        scanned = 0
        cutoff = (date.today() - timedelta(days=400)).isoformat()
        for market in MARKETS:
            heat = heats.get(market) or {}
            top50 = []
            if heat.get('tradeDate'):
                raw_top = await MarketHeatDao.list_top50(db, market, str(heat['tradeDate']))
                top50 = [
                    {'symbol': r.symbol, 'name': r.name, 'market': market, 'category': 'listed'} for r in raw_top
                ]
            candidates = merge_candidates(top50, _featured_for_market(market), cap=CANDIDATE_CAP)
            symbols = [c['symbol'] for c in candidates]
            kline_map = await StockPickDao.load_recent_daily_klines(db, symbols, cutoff)
            sent_raw = sentiment.get(SENTIMENT_FIELD[market])
            heat_score = heat.get('heatScore')
            opened = market in open_markets
            for cand in candidates:
                scanned += 1
                klines = kline_map.get(cand['symbol']) or []
                computed = FactorService.compute_from_klines(klines)
                if not computed.get('ok'):
                    continue
                metrics = computed.get('metrics') or {}
                score = computed.get('score') or {}
                decision = decide_signal(score)
                pick_score = combine_pick_score(
                    score.get('total'),
                    sentiment_raw=sent_raw,
                    heat_score=heat_score,
                    index_open=opened,
                    index_change_pct=index_chg.get(market),
                )
                reco, stance = reco_from_signal(decision.get('signal'), pick_score)
                tags = list(score.get('tags') or [])[:6]
                if opened:
                    tags.append('盘中含指数')
                else:
                    tags.append('休市无指数')
                scored.append(
                    {
                        'symbol': cand['symbol'],
                        'name': cand.get('name') or cand['symbol'],
                        'market': market,
                        'price': metrics.get('latestClose'),
                        'changePct': metrics.get('dayChangePercent'),
                        'factorScore': score.get('total'),
                        'pickScore': pick_score,
                        'signal': decision.get('signal'),
                        'recommendation': reco,
                        'stance': stance,
                        'confidence': decision.get('confidence'),
                        'reason': decision.get('reason'),
                        'summary': decision.get('reason'),
                        'indicatorReview': '、'.join(tags) or '指标中性',
                        'sentimentReview': sentiment.get('summary') or '暂无舆情',
                        'operationAdvice': reco,
                        'riskWarning': '无',
                        'tags': tags,
                        'source': 'rule',
                        'metrics': {
                            'rsi14': metrics.get('rsi14'),
                            'macdHist': metrics.get('macdHist'),
                            'ma20': metrics.get('ma20'),
                            'volumeRatio20': metrics.get('volumeRatio20'),
                            'return20': metrics.get('return20'),
                        },
                    }
                )

        picked = select_top_picks(scored, per_market=PICKS_PER_MARKET)
        ai_cfg = await cls._resolve_ai(db) if use_ai else {'available': False, 'reason': '未启用 AI'}
        ai_count = 0
        model_name = ai_cfg.get('modelName')
        ai_error = ai_cfg.get('reason')
        if ai_cfg.get('available'):
            context = {
                'markets': {
                    m: {
                        'open': m in open_markets,
                        'heatScore': (heats.get(m) or {}).get('heatScore'),
                        'indexChangePct': index_chg.get(m),
                        'sentiment': sentiment.get(SENTIMENT_FIELD[m]),
                    }
                    for m in MARKETS
                },
                'sentiment': sentiment,
            }
            ai_count, ai_error = await cls._enrich_picked_with_ai(picked, ai_cfg, context)
        elif use_ai:
            logger.warning(f'[选股] 跳过 AI：{ai_error}')

        db_rows = [
            {
                'rank_no': int(row.get('rankNo') or 0),
                'symbol': row['symbol'],
                'name': row.get('name'),
                'market': row['market'],
                'price': row.get('price'),
                'change_pct': row.get('changePct'),
                'factor_score': row.get('factorScore'),
                'pick_score': row.get('pickScore'),
                'signal': row.get('signal'),
                'recommendation': row.get('recommendation'),
                'stance': row.get('stance'),
                'confidence': row.get('confidence'),
                'summary': row.get('summary'),
                'indicator_review': row.get('indicatorReview'),
                'sentiment_review': row.get('sentimentReview'),
                'operation_advice': row.get('operationAdvice'),
                'risk_warning': row.get('riskWarning'),
                'tags_json': json.dumps(row.get('tags') or [], ensure_ascii=False),
                'source': row.get('source') or 'rule',
                'factor_json': json.dumps(row.get('metrics') or {}, ensure_ascii=False),
            }
            for row in picked
        ]
        await StockPickDao.replace_items(db, pick_id, db_rows)
        status = 'empty' if not picked else ('partial' if use_ai and ai_count < len(picked) else 'ok')
        hint = mood.get('hint') or ''
        ai_part = f'AI {ai_count}/{len(picked)}'
        if model_name:
            ai_part += f'（{model_name}）'
        if use_ai and ai_count == 0 and ai_error:
            ai_part += f'，未写入研判：{ai_error}'
        message = f'{hint} 扫描{scanned}只，入选{len(picked)}只，{ai_part}。'
        await StockPickDao.upsert_run(
            db,
            {
                'trade_date': trade_date,
                'status': status,
                'trigger_source': trigger,
                'scanned_count': scanned,
                'picked_count': len(picked),
                'ai_count': ai_count,
                'model_name': model_name,
                'open_markets': ','.join(sorted(open_markets)),
                'message': message[:500],
            },
        )
        await db.commit()
        logger.info(f'[选股] {message}')
        return await cls.get_latest_services(db)
