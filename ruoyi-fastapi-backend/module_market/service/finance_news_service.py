"""
财经资讯简报服务：聚合内部市场脉冲/技术扫描/推荐 + 外部 Google News RSS + 舆情新闻。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import desc, select

from module_market.dao.market_dao import FinanceBriefingDao
from module_market.service.indicator_service import IndicatorService
from module_quant.entity.do.quant_do import QuantStrategyRun, QuantStrategySignal
from utils.time_format_util import now_beijing
from module_sentiment.entity.do.sentiment_do import SentimentNews
from utils.common_util import CamelCaseUtil
from utils.influx_util import InfluxUtil
from utils.log_util import logger

# 指数趋势判断所需最少K线数（前收 + 最新）
_MIN_BARS_FOR_TREND = 2

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from module_market.entity.do.market_do import FinanceBriefing


class FinanceNewsService:
    """财经资讯简报服务"""

    MARKET_LABELS = {'US': '美股', 'CN': 'A股', 'HK': '港股'}
    EXTERNAL_NEWS_QUERIES = {
        'US': 'US stock market OR Nasdaq OR S&P 500 OR Federal Reserve',
        'CN': 'A-share market OR China stocks OR CSI 300 OR Shanghai Composite',
        'HK': 'Hong Kong stocks OR Hang Seng OR China Hong Kong market',
    }
    # 各市场代表性指数（内部扫描用）
    MARKET_BENCHMARKS = {
        'US': [('^GSPC', 'S&P500'), ('^IXIC', 'Nasdaq'), ('^DJI', 'Dow')],
        'CN': [],
        'HK': [],
    }
    # 舆情关键词粗分市场
    MARKET_KEYWORDS = {
        'US': ['美股', '纳斯达克', '道琼斯', '标普', '美联储', '华尔街', 'Nasdaq', 'Fed'],
        'CN': ['A股', '沪指', '深成指', '创业板', '科创板', '上证', 'A 股'],
        'HK': ['港股', '恒生', '恒指', '港交所', '南向'],
    }

    @classmethod
    async def get_briefings(
        cls, query_db: AsyncSession, limit: int = 20, market: str | None = None, refresh: bool = False
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit or 20), 60))
        market = market.upper() if market else None
        upstream_message = None
        try:
            if refresh:
                await cls.refresh_all_markets(query_db)
            rows = await FinanceBriefingDao.get_latest(query_db, limit=limit, market=market)
            # 若库空且未强制刷新，尝试生成一次
            if not rows and not refresh:
                await cls.refresh_all_markets(query_db)
                rows = await FinanceBriefingDao.get_latest(query_db, limit=limit, market=market)
        except Exception as exc:
            logger.warning(f'[财经资讯] 简报聚合失败: {exc}')
            rows = []
            upstream_message = '财经资讯源暂时不可用，已返回空列表，请稍后重试'

        data = [
            {
                'id': r.id,
                'market': r.market,
                'briefingType': r.briefing_type,
                'headline': r.headline,
                'summary': r.summary,
                'sourceName': r.source_name,
                'sourceLink': r.source_link,
                'payload': cls._json_load(r.payload_json),
                'generatedAt': r.generated_at.strftime('%Y-%m-%d %H:%M:%S') if r.generated_at else None,
                'expiresAt': r.expires_at.strftime('%Y-%m-%d %H:%M:%S') if r.expires_at else None,
            }
            for r in rows
        ]
        google_status = getattr(cls, '_last_google_status', None)
        if google_status and not google_status.get('ok'):
            upstream_message = upstream_message or google_status.get('message')
        return {
            'success': True,
            'data': data,
            'message': upstream_message,
            'meta': {
                'market': market,
                'count': len(data),
                'limit': limit,
                'snapshotAt': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
                'sources': sorted({d['sourceName'] for d in data if d.get('sourceName')}),
                'googleNews': google_status,
                'message': upstream_message,
            },
        }

    @classmethod
    async def refresh_all_markets(cls, query_db: AsyncSession) -> dict[str, Any]:
        """刷新 US/CN/HK 简报流并清理过期数据"""
        generated: list[dict[str, Any]] = []
        now = datetime.now()
        for market in ('US', 'CN', 'HK'):
            generated.extend(await cls._build_internal_items(query_db, market, now))
            generated.extend(await cls._fetch_google_news(query_db, market, now))
            generated.extend(await cls._pull_sentiment_news(query_db, market, now))
        # 推荐关注按信号标的的真实市场归属打标，只生成一次（放循环里会把同一批信号错误复制成三个市场）
        generated.extend(await cls._build_recommendation_items(query_db, now))

        # 同批次内跨来源去重（recent_duplicate 只查已落库数据，本轮生成的要在这里兜住）
        seen_keys: set[tuple[str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for item in generated:
            key = (item['market'], item['briefing_type'], item['headline'])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)
        generated = deduped

        if generated:
            await FinanceBriefingDao.add_batch(query_db, generated)
        await FinanceBriefingDao.prune_older_than(query_db, now - timedelta(days=5))
        await query_db.commit()
        logger.info(f'[财经资讯] 刷新完成，写入{len(generated)}条')
        return {'generatedAt': now.strftime('%Y-%m-%d %H:%M:%S'), 'count': len(generated)}

    # ------------------------------------------------------------------ internal

    @classmethod
    async def _build_internal_items(  # noqa: PLR0912, PLR0915 - 多源聚合逻辑内聚，拆分会打断事务语义
        cls, query_db: AsyncSession, market: str, now: datetime
    ) -> list[dict[str, Any]]:
        label = cls.MARKET_LABELS.get(market, market)
        expires = now + timedelta(minutes=30)
        items: list[dict[str, Any]] = []

        # 市场脉冲：取基准指数近况（Influx 不可用时跳过，不阻断外部新闻）
        benchmarks = cls.MARKET_BENCHMARKS.get(market) or []
        insight_bits: list[str] = []
        market_score = None
        loop = asyncio.get_running_loop()
        for sym, name in benchmarks[:3]:
            try:
                # Influx同步网络IO，放线程池避免阻塞事件循环
                klines = await loop.run_in_executor(None, InfluxUtil.query_klines, market, sym, '-30d', 'now()')
            except Exception as exc:
                logger.warning(f'[财经资讯] 读取指数K线失败 {sym}: {exc}')
                klines = []
            if len(klines) < _MIN_BARS_FOR_TREND:
                continue
            prev, last = klines[-2], klines[-1]
            chg = None
            try:
                if prev.get('close') and last.get('close'):
                    chg = (float(last['close']) - float(prev['close'])) / float(prev['close']) * 100
            except (TypeError, ValueError, ZeroDivisionError):
                chg = None
            if chg is not None:
                insight_bits.append(f"{name} {chg:+.2f}%")
                if market_score is None:
                    market_score = round(chg, 2)

        headline = f'{label}市场脉冲'
        summary = '；'.join(insight_bits) if insight_bits else f'{label}暂无新的市场动态。'
        items.append(
            cls._row(
                market,
                'market-insight',
                headline,
                summary,
                'market-insight',
                None,
                {'marketScore': market_score, 'benchmarks': insight_bits},
                now,
                expires,
            )
        )

        # 技术扫描：对第一个有数据的基准算指标快照
        tech_score = None
        tech_summary = f'{label}技术扫描暂无数据'
        for sym, name in benchmarks[:1] or [(None, None)]:
            if not sym:
                break
            try:
                klines = await loop.run_in_executor(None, InfluxUtil.query_klines, market, sym, '-1y', 'now()')
            except Exception as exc:
                logger.warning(f'[财经资讯] 技术扫描K线失败 {sym}: {exc}')
                klines = []
            if not klines:
                continue
            # pandas指标计算属CPU密集，同样放线程池
            snap = await loop.run_in_executor(None, IndicatorService.latest_snapshot, klines)
            rsi = (snap.get('rsi') or {}).get('rsi12') or (snap.get('rsi') or {}).get('rsi6')
            macd = (snap.get('macd') or {}).get('macd')
            close = snap.get('close')
            # 简易技术分：RSI 中性附近 50，MACD>0 加分
            score = 50.0
            try:
                if rsi is not None:
                    score += (float(rsi) - 50) * 0.4
                if macd is not None and float(macd) > 0:
                    score += 8
                elif macd is not None:
                    score -= 8
            except (TypeError, ValueError):
                pass
            tech_score = round(max(0, min(100, score)), 1)
            rsi_text = f'{float(rsi):.1f}' if rsi is not None else '--'
            tech_summary = f'{name} 收盘{close}，RSI={rsi_text}，技术评分{tech_score}'
            items.append(
                cls._row(
                    market,
                    'market-ai-scan',
                    f'{label}技术扫描',
                    tech_summary,
                    'daily-market-scan',
                    None,
                    {
                        'technicalScore': tech_score,
                        'breadthRatio': None,
                        'rsi': rsi,
                        'close': close,
                    },
                    now,
                    expires,
                )
            )
            break
        else:
            items.append(
                cls._row(
                    market,
                    'market-ai-scan',
                    f'{label}技术扫描',
                    tech_summary,
                    'daily-market-scan',
                    None,
                    {'technicalScore': tech_score, 'breadthRatio': None},
                    now,
                    expires,
                )
            )

        return items

    @classmethod
    async def _build_recommendation_items(
        cls, query_db: AsyncSession, now: datetime
    ) -> list[dict[str, Any]]:
        """从最近一次策略运行中取 BUY 信号作为推荐关注，市场归属以标的元数据为准"""
        from module_market.entity.do.market_do import MarketInstrument  # noqa: PLC0415 - 按需加载 ORM 映射

        latest_run = (
            await query_db.execute(select(QuantStrategyRun).order_by(desc(QuantStrategyRun.create_time)).limit(1))
        ).scalars().first()
        if not latest_run:
            return []
        signals = (
            await query_db.execute(
                select(QuantStrategySignal)
                .where(QuantStrategySignal.run_id == latest_run.run_id, QuantStrategySignal.signal == 'BUY')
                .order_by(desc(QuantStrategySignal.score))
                .limit(3)
            )
        ).scalars().all()
        if not signals:
            return []
        # 信号表不存市场字段，从标的元数据反查；查不到默认US
        symbol_markets: dict[str, str] = {}
        instruments = (
            await query_db.execute(
                select(MarketInstrument.symbol, MarketInstrument.market).where(
                    MarketInstrument.symbol.in_([s.symbol for s in signals])
                )
            )
        ).all()
        for sym, mkt in instruments:
            symbol_markets[sym] = (mkt or 'US').upper()
        expires = now + timedelta(minutes=60)
        items = []
        for s in signals:
            sig_market = symbol_markets.get(s.symbol, 'US')
            label = cls.MARKET_LABELS.get(sig_market, sig_market)
            items.append(
                cls._row(
                    sig_market,
                    'recommendation',
                    f'{label}推荐关注 {s.symbol}',
                    s.reason or f'{s.symbol} 策略评分 {s.score}',
                    'quant-strategy',
                    None,
                    {
                        'symbol': s.symbol,
                        'score': s.score,
                        'confidence': s.confidence,
                        'signal': s.signal,
                    },
                    now,
                    expires,
                )
            )
        return items

    # ------------------------------------------------------------------ external

    @classmethod
    async def _fetch_google_news(
        cls, query_db: AsyncSession, market: str, now: datetime
    ) -> list[dict[str, Any]]:
        query = cls.EXTERNAL_NEWS_QUERIES.get(market)
        if not query:
            return []
        url = f'https://news.google.com/rss/search?q={quote_plus(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans'
        try:
            async with httpx.AsyncClient(timeout=12.0, trust_env=False) as client:
                resp = await client.get(url, headers={'User-Agent': 'Mozilla/5.0 RuoYi-Sentiment/1.0'})
                if resp.status_code in {429, 500, 502, 503, 504}:
                    cls._last_google_status = {
                        'ok': False,
                        'status': resp.status_code,
                        'message': 'Google News 暂时不可用（上游超时或限流），已跳过外部资讯',
                    }
                    logger.warning(f'[财经资讯] Google News RSS HTTP {resp.status_code} market={market}')
                    return []
                resp.raise_for_status()
                text = resp.text
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
            cls._last_google_status = {
                'ok': False,
                'status': getattr(getattr(exc, 'response', None), 'status_code', None),
                'message': 'Google News 暂时不可用（上游超时或限流），已跳过外部资讯',
            }
            logger.warning(f'[财经资讯] Google News RSS 拉取失败 market={market}: {exc}')
            return []
        except Exception as exc:
            cls._last_google_status = {
                'ok': False,
                'status': None,
                'message': 'Google News 暂时不可用，已跳过外部资讯',
            }
            logger.warning(f'[财经资讯] Google News RSS 拉取失败 market={market}: {exc}')
            return []
        cls._last_google_status = {'ok': True, 'status': 200, 'message': None}

        try:
            root = ET.fromstring(text)
        except Exception as exc:
            logger.warning(f'[财经资讯] RSS 解析失败: {exc}')
            return []

        expires = now + timedelta(minutes=90)
        since = now - timedelta(hours=6)
        items_parsed: list[tuple[str, str, str | None]] = []
        for item in root.findall('.//channel/item')[:5]:
            headline = (item.findtext('title') or '').strip()[:190]
            summary = cls._strip_html(item.findtext('description') or '')[:800]
            source_link = (item.findtext('link') or '').strip() or None
            if not headline:
                continue
            items_parsed.append((headline, summary, source_link))
        # 批量查重：一次查询替代逐条 recent_duplicate
        duplicates = await FinanceBriefingDao.filter_duplicates(
            query_db, market, [h for h, _, _ in items_parsed], since
        )
        rows: list[dict[str, Any]] = []
        for headline, summary, source_link in items_parsed:
            if headline in duplicates:
                continue
            rows.append(
                cls._row(
                    market,
                    'market-news',
                    headline,
                    summary or f'{cls.MARKET_LABELS.get(market, market)}市场外部资讯',
                    'Google News RSS',
                    source_link,
                    {'kind': 'external-news', 'source': 'google-news-rss'},
                    now,
                    expires,
                )
            )
        return rows

    @classmethod
    async def _pull_sentiment_news(
        cls, query_db: AsyncSession, market: str, now: datetime
    ) -> list[dict[str, Any]]:
        """把舆情模块近期新闻按关键词映射到市场，写入简报流"""
        keywords = cls.MARKET_KEYWORDS.get(market) or []
        news_rows = (
            await query_db.execute(
                select(SentimentNews).order_by(desc(SentimentNews.pub_time)).limit(40)
            )
        ).scalars().all()
        expires = now + timedelta(minutes=90)
        since = now - timedelta(hours=6)
        candidates: list[tuple[dict[str, Any], str]] = []
        for n in news_rows:
            title = (n.title or '').strip()
            content = (n.content or '')[:800]
            if not title:
                continue
            # 无关键词时 CN 默认全收；有关键词则匹配
            if (
                keywords
                and not any(k.lower() in (title + content).lower() for k in keywords)
                and market != 'CN'
            ):
                # 未匹配时仅 CN 放宽接收无明确市场标签的中文资讯，其余市场直接跳过
                continue
            row = cls._row(
                market,
                'market-news',
                title[:190],
                content or title,
                f'sentiment-{n.source}' if n.source else 'sentiment',
                n.url,
                {'kind': 'sentiment-news', 'newsId': n.news_id},
                now,
                expires,
            )
            candidates.append((row, title[:190]))
        # 批量查重：一次查询替代逐条 recent_duplicate
        duplicates = await FinanceBriefingDao.filter_duplicates(
            query_db, market, [t for _, t in candidates], since
        )
        rows = [row for row, t in candidates if t not in duplicates][:5]
        return rows

    # ------------------------------------------------------------------ helpers

    @classmethod
    def _row(
        cls,
        market: str,
        briefing_type: str,
        headline: str,
        summary: str,
        source_name: str,
        source_link: str | None,
        payload: dict[str, Any],
        generated_at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any]:
        return {
            'market': market,
            'briefing_type': briefing_type,
            'headline': (headline or '')[:255],
            'summary': summary or '',
            'source_name': source_name or 'system',
            'source_link': (source_link or None) and str(source_link)[:2048],
            'payload_json': json.dumps(payload or {}, ensure_ascii=False),
            'generated_at': generated_at,
            'expires_at': expires_at,
        }

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r'<[^>]+>', '', text or '').strip()

    @staticmethod
    def _json_load(raw: str | None) -> Any:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    @classmethod
    def serialize_briefing(cls, row: FinanceBriefing) -> dict[str, Any]:
        return CamelCaseUtil.transform_result(row)
