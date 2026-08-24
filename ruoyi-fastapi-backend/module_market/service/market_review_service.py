"""三市场收盘日报：采集指数/代表股、资讯、舆情后调用 AI（失败则规则兜底）。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ServiceException
from module_ai.dao.ai_model_dao import AiModelDao
from module_market.constant.instruments import TARGET_INSTRUMENTS
from module_market.dao.market_dao import FinanceBriefingDao, MarketDailyReviewDao
from module_market.service.finance_news_service import FinanceNewsService
from module_market.service.market_review_analyzer import MarketReviewAiAnalyzer, rule_based_market_review
from module_market.service.market_service import MarketService
from module_sentiment.entity.do.sentiment_do import SentimentNews
from utils.crypto_util import CryptoUtil
from utils.influx_util import InfluxUtil
from utils.log_util import logger

MARKET_LABELS = {'US': '美股', 'HK': '港股', 'CN': 'A股'}
MARKET_BENCHMARKS = {
    'US': [('^DJI', '道指'), ('^GSPC', '标普500'), ('^IXIC', '纳指')],
    'HK': [('0700.HK', '腾讯'), ('9988.HK', '阿里'), ('3690.HK', '美团'), ('0005.HK', '汇丰')],
    'CN': [('600519', '茅台'), ('300750', '宁德时代'), ('601318', '平安'), ('000858', '五粮液')],
}


def _dump(payload: Any, limit: int = 60000) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)[:limit]


def _fmt_dt(value: datetime | None) -> str | None:
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


class MarketReviewService:
    @classmethod
    def serialize(cls, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            'reviewId': row.review_id,
            'market': row.market,
            'marketLabel': MARKET_LABELS.get((row.market or '').upper(), row.market),
            'tradeDate': row.trade_date,
            'title': row.title,
            'stance': row.stance,
            'score': row.score,
            'summary': row.summary,
            'indexReview': row.index_review,
            'newsReview': row.news_review,
            'sentimentReview': row.sentiment_review,
            'outlook': row.outlook,
            'riskWarning': row.risk_warning,
            'source': row.source,
            'modelName': row.model_name,
            'analysisTime': _fmt_dt(row.analysis_time),
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
            logger.warning(f'[市场复盘] 解析 AI 模型失败: {exc}')
        return {
            'baseUrl': base_url,
            'apiKey': api_key,
            'modelName': model_name,
            'temperature': temperature,
            'available': bool(base_url and api_key and model_name),
        }

    @classmethod
    def _normalize_result(cls, parsed: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
        data = dict(fallback)
        if not parsed:
            return data
        for key in (
            'title',
            'stance',
            'score',
            'summary',
            'index_review',
            'news_review',
            'sentiment_review',
            'outlook',
            'risk_warning',
            'key_points',
        ):
            if parsed.get(key) not in (None, ''):
                data[key] = parsed[key]
        if data.get('stance') not in {'偏多', '偏空', '中性'}:
            data['stance'] = fallback.get('stance') or '中性'
        try:
            data['score'] = max(0, min(100, int(data.get('score') or 50)))
        except (TypeError, ValueError):
            data['score'] = fallback.get('score') or 50
        return data

    @classmethod
    async def _collect_context(cls, query_db: AsyncSession, market: str) -> dict[str, Any]:
        market = market.upper()
        benches_meta = MARKET_BENCHMARKS.get(market) or []
        symbols = [s for s, _n in benches_meta]
        grouped = await asyncio.to_thread(InfluxUtil.query_latest_klines, market, symbols, 2, '-60d')
        benchmarks = []
        trade_date = datetime.now().strftime('%Y-%m-%d')
        for symbol, name in benches_meta:
            quote = MarketService._build_quote_from_klines(grouped.get(symbol) or [])
            if quote.get('tradeDate'):
                trade_date = str(quote['tradeDate'])[:10]
            change = quote.get('changeRate')
            try:
                change_n = float(change)
                change_text = f"{'+' if change_n >= 0 else ''}{change_n:.2f}%"
            except (TypeError, ValueError):
                change_n = None
                change_text = '--'
            benchmarks.append(
                {
                    'symbol': symbol,
                    'name': name,
                    'last': quote.get('last'),
                    'changeRate': change_n,
                    'changeText': change_text,
                    'tradeDate': quote.get('tradeDate'),
                }
            )

        pool = [item[0] for item in TARGET_INSTRUMENTS if item[2] == market and not str(item[0]).startswith('^')]
        pool = pool[:24]
        up_count = down_count = 0
        if pool:
            bars = await asyncio.to_thread(InfluxUtil.query_latest_klines, market, pool, 2, '-60d')
            for symbol in pool:
                q = MarketService._build_quote_from_klines(bars.get(symbol) or [])
                try:
                    chg = float(q.get('changeRate'))
                except (TypeError, ValueError):
                    continue
                if chg > 0:
                    up_count += 1
                elif chg < 0:
                    down_count += 1

        news_rows = []
        try:
            briefings = await FinanceBriefingDao.get_latest(query_db, limit=8, market=market)
            for row in briefings:
                news_rows.append(
                    {
                        'headline': row.headline,
                        'summary': (row.summary or '')[:200],
                        'source': row.source_name,
                    }
                )
        except Exception as exc:
            logger.info(f'[市场复盘] 资讯跳过: {exc}')

        keywords = FinanceNewsService.MARKET_KEYWORDS.get(market) or []
        sentiment_rows = []
        try:
            news = (
                (await query_db.execute(select(SentimentNews).order_by(desc(SentimentNews.create_time)).limit(40)))
                .scalars()
                .all()
            )
            for item in news:
                blob = f'{item.title or ""} {item.content or ""}'
                if keywords and not any(k.lower() in blob.lower() for k in keywords):
                    continue
                sentiment_rows.append({'title': item.title, 'source': item.source, 'content': (item.content or '')[:160]})
                if len(sentiment_rows) >= 8:
                    break
        except Exception as exc:
            logger.info(f'[市场复盘] 舆情跳过: {exc}')

        return {
            'market': market,
            'marketLabel': MARKET_LABELS.get(market, market),
            'tradeDate': trade_date,
            'benchmarks': benchmarks,
            'upCount': up_count,
            'downCount': down_count,
            'sampleCount': up_count + down_count,
            'news': news_rows,
            'sentiment': sentiment_rows,
        }

    @classmethod
    async def analyze_market(cls, query_db: AsyncSession, market: str, ai_conf: dict[str, Any] | None = None) -> dict[str, Any]:
        market = (market or 'US').strip().upper()
        if market not in MARKET_LABELS:
            raise ServiceException(message=f'不支持的市场: {market}')
        context = await cls._collect_context(query_db, market)
        fallback = rule_based_market_review(context)
        ai_conf = ai_conf if ai_conf is not None else await cls._resolve_ai(query_db)
        parsed = None
        source = 'rule'
        model_name = None
        message = '已用指标与资讯生成兜底复盘'
        if ai_conf.get('available'):
            ai_result = await MarketReviewAiAnalyzer.analyze(
                ai_conf['baseUrl'],
                ai_conf['apiKey'],
                ai_conf['modelName'],
                context,
                temperature=float(ai_conf.get('temperature') or 0.2),
            )
            if ai_result.get('ok'):
                parsed = ai_result.get('result')
                source = 'ai'
                model_name = ai_conf.get('modelName')
                message = '分析成功'
            else:
                message = f'模型失败，已回退指标复盘: {ai_result.get("error")}'
        result = cls._normalize_result(parsed, fallback)
        row = await MarketDailyReviewDao.upsert(
            query_db,
            {
                'market': market,
                'trade_date': context.get('tradeDate'),
                'title': result.get('title'),
                'stance': result.get('stance'),
                'score': result.get('score'),
                'summary': result.get('summary'),
                'index_review': result.get('index_review'),
                'news_review': result.get('news_review'),
                'sentiment_review': result.get('sentiment_review'),
                'outlook': result.get('outlook'),
                'risk_warning': result.get('risk_warning'),
                'source': source,
                'model_name': model_name,
                'context_json': _dump(context),
                'raw_json': _dump(parsed or {'fallback': fallback}),
                'analysis_time': datetime.now(),
            },
        )
        payload = cls.serialize(row) or {}
        await query_db.commit()
        payload.update({'ok': True, 'message': message, 'keyPoints': result.get('key_points') or []})
        return payload

    @classmethod
    async def analyze_markets(cls, query_db: AsyncSession, markets: list[str] | None = None) -> dict[str, Any]:
        targets = [m.upper() for m in (markets or list(MARKET_LABELS)) if m.upper() in MARKET_LABELS]
        if not targets:
            targets = list(MARKET_LABELS)
        ai_conf = await cls._resolve_ai(query_db)
        items = []
        failed = []
        for market in targets:
            try:
                items.append(await cls.analyze_market(query_db, market, ai_conf=ai_conf))
            except Exception as exc:
                logger.warning(f'[市场复盘] {market} 失败: {exc}')
                failed.append({'market': market, 'reason': str(exc)})
                try:
                    await query_db.rollback()
                except Exception:
                    pass
        return {
            'ok': len(failed) == 0,
            'count': len(items),
            'failedCount': len(failed),
            'aiAvailable': bool(ai_conf.get('available')),
            'items': items,
            'failed': failed,
            'message': f'完成 {len(items)} 个市场，失败 {len(failed)} 个',
        }

    @classmethod
    async def latest_services(cls, query_db: AsyncSession) -> dict[str, Any]:
        rows = await MarketDailyReviewDao.list_latest(query_db)
        items = [cls.serialize(r) for r in rows]
        by_market = {it['market']: it for it in items if it}
        ordered = [by_market.get(m) for m in ('US', 'HK', 'CN') if by_market.get(m)]
        ai_conf = await cls._resolve_ai(query_db)
        return {
            'items': ordered,
            'count': len(ordered),
            'aiAvailable': bool(ai_conf.get('available')),
            'aiHint': None
            if ai_conf.get('available')
            else '未配置可用 AI 模型，收盘复盘将使用指数涨跌与资讯兜底。请在「AI 模型管理」填写连接。',
        }

    @classmethod
    async def history_services(
        cls, query_db: AsyncSession, market: str | None = None, limit: int = 60
    ) -> dict[str, Any]:
        rows = await MarketDailyReviewDao.list_history(query_db, market=market, limit=limit)
        return {'items': [cls.serialize(r) for r in rows], 'count': len(rows)}
