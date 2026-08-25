"""
行情数据中心模块服务层：编排标的元数据、K线查询、指标计算、同步、AI分析、详情概览。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from module_market.constant.instruments import TARGET_INSTRUMENTS, get_instrument_meta
from module_market.dao.market_dao import MarketInstrumentDao, SymbolAiAnalysisDao
from module_market.entity.vo.market_vo import (
    IndicatorQueryModel,
    KlineQueryModel,
    MarketAiAnalyzeModel,
    MarketInstrumentModel,
    MarketInstrumentQueryModel,
    MarketInstrumentUniverseQueryModel,
    MarketSyncModel,
)
from module_market.service.content_cache_service import SymbolContentService
from module_market.service.finance_news_service import FinanceNewsService
from module_market.service.indicator_service import IndicatorService
from utils.time_format_util import now_beijing
from module_market.service.kline_period import (
    default_range_start,
    is_minute_period,
    normalize_kline_period,
    resample_how,
)
from module_market.service.listing_service import ListingService
from module_market.service.stock_pick_service import StockPickService
from module_market.service.sync_service import MarketSyncService
from module_market.service.tradingview_service import _resample_klines
from module_quant.dao.quant_dao import QuantStrategyDao
from utils.common_util import CamelCaseUtil
from utils.influx_util import InfluxUtil
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.quote_util import build_quote_from_klines

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

# RSI 超买/超卖阈值
_RSI_OVERBOUGHT = 70
_RSI_OVERSOLD = 30

BOARD_QUOTES_CACHE_KEY = 'sfp:cache:board:quotes'
# 看板缓存兜底过期时间；正常由 jobs 周期刷新，jobs 中断时最多滞后 15 分钟再降级到 scheduled 数据
BOARD_QUOTES_TTL_SECONDS = 15 * 60

# Common Service pattern - will use BaseService in future


class MarketService:
    """Market Service - using common template pattern"""
    dao = None  # Will be set with BaseService in future

    """
    行情数据中心服务层
    """


    # ---------- 标的元数据 ----------

    @classmethod
    async def init_instruments_services(cls, query_db: AsyncSession) -> int:
        """
        初始化/upsert目标标的清单到 market_instrument 表，返回新增条数。
        """
        instruments = [
            {'symbol': s, 'name': n, 'market': m, 'category': c} for s, n, m, c in TARGET_INSTRUMENTS
        ]
        try:
            added = await MarketInstrumentDao.upsert_instruments(query_db, instruments)
            await query_db.commit()
            logger.info(f'[行情] 初始化目标标的完成，新增{added}条')
            return added
        except Exception as e:
            await query_db.rollback()
            raise e

    @classmethod
    async def sync_listings_services(cls, markets: list[str] | None = None) -> dict[str, Any]:
        """抓取美股/A股/港股全市场代码写入 market_instrument（listed），不覆盖精选分类。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, ListingService.sync, markets)

    @classmethod
    async def sync_listings_from_influx_services(cls, markets: list[str] | None = None) -> dict[str, Any]:
        """从 Influx 已有序列同步全市场代码到 market_instrument（listed）。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, ListingService.sync_from_influx, markets)

    @classmethod
    async def get_instrument_list_services(
        cls, query_db: AsyncSession, query_object: MarketInstrumentQueryModel
    ) -> list[dict[str, Any]]:
        """
        获取标的列表service（若表为空则先初始化目标标的）。
        """
        existing = await MarketInstrumentDao.get_all_symbols(query_db)
        missing = [item[0] for item in TARGET_INSTRUMENTS if item[0] not in existing]
        if not existing or missing:
            await cls.init_instruments_services(query_db)
        rows = await MarketInstrumentDao.get_instrument_list(query_db, query_object)
        return [
            MarketInstrumentModel(**CamelCaseUtil.transform_result(r)).model_dump(by_alias=True) for r in rows
        ]

    @classmethod
    async def get_instrument_universe_services(
        cls, query_db: AsyncSession, query_object: MarketInstrumentUniverseQueryModel
    ) -> tuple[Any, dict[str, int]]:
        """全市场分页列表 + 三市场计数。当前页附带日K最新价，不扫全表。"""
        page = await MarketInstrumentDao.get_instrument_universe(query_db, query_object)
        rows = list(page.rows or [])
        symbols = [str(r.get('symbol')) for r in rows if r.get('symbol')]
        quotes = await MarketInstrumentDao.get_latest_daily_quotes(query_db, symbols)
        for row in rows:
            q = quotes.get(str(row.get('symbol') or '')) or {}
            row['price'] = q.get('price')
            row['prevClose'] = q.get('prevClose')
            row['changeRate'] = q.get('changeRate')
            row['tradeDate'] = q.get('tradeDate')
            row['volume'] = q.get('volume')
            row['up'] = q.get('up')
        page.rows = rows
        counts = await MarketInstrumentDao.get_instrument_market_counts(query_db)
        return page, counts

    # ---------- K线 ----------

    @classmethod
    def _filter_board_payload(
        cls,
        payload: dict[str, Any],
        category: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        quotes = list(payload.get('quotes') or [])
        if market:
            mkt = market.strip().upper()
            quotes = [q for q in quotes if str(q.get('market') or '').upper() == mkt]
        if category:
            cat = category.strip()
            quotes = [q for q in quotes if str(q.get('category') or '') == cat]
        indices = [q for q in quotes if q.get('category') == 'index' or str(q.get('symbol') or '').startswith('^')]
        index_symbols = {q['symbol'] for q in indices}
        rows = [q for q in quotes if q.get('symbol') not in index_symbols]
        filtered = dict(payload)
        filtered['quotes'] = quotes
        filtered['indices'] = indices
        filtered['rows'] = rows
        filtered['count'] = len(quotes)
        return filtered

    @classmethod
    async def get_board_quotes_services(
        cls,
        query_db: AsyncSession,
        category: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        """
        只读 Redis/SWR 缓存。全市场 Influx 扫描只允许在 jobs 里执行。
        """
        cached = await cache_get_json(BOARD_QUOTES_CACHE_KEY)
        if isinstance(cached, dict) and (cached.get('quotes') or cached.get('rows')):
            payload = cls._filter_board_payload(cached, category=category, market=market)
            payload['source'] = payload.get('source') or 'cache'
            payload['stale'] = False
            return payload

        from module_quant.service.readmodel_service import ReadModelService  # noqa: PLC0415 - 避免循环导入

        scheduled = await ReadModelService.get_scheduled('board')
        if isinstance(scheduled, dict) and scheduled.get('items'):
            adapted = cls._adapt_scheduled_board(scheduled)
            payload = cls._filter_board_payload(adapted, category=category, market=market)
            payload['source'] = 'scheduled'
            payload['stale'] = True
            return payload

        return {
            'quotes': [],
            'indices': [],
            'rows': [],
            'source': 'empty',
            'stale': True,
            'count': 0,
            'message': '看板缓存尚未生成，请等待 jobs 预热',
        }

    @classmethod
    def _adapt_scheduled_board(cls, scheduled: dict[str, Any]) -> dict[str, Any]:
        quotes: list[dict[str, Any]] = []
        for item in scheduled.get('items') or []:
            change_rate = item.get('changeRate')
            quotes.append(
                {
                    'symbol': item.get('symbol'),
                    'name': item.get('name'),
                    'market': item.get('market'),
                    'category': item.get('category'),
                    'price': item.get('close') if item.get('close') is not None else item.get('price'),
                    'change': item.get('change'),
                    'changeRate': change_rate,
                    'volume': item.get('volume'),
                    'tradeDate': item.get('asOf') or item.get('tradeDate'),
                    'changeText': (
                        f"{'+' if change_rate >= 0 else ''}{change_rate:.2f}%"
                        if isinstance(change_rate, (int, float))
                        else '--'
                    ),
                    'up': True if change_rate is None else change_rate >= 0,
                    'source': 'scheduled',
                }
            )
        return {
            'quotes': quotes,
            'asOf': scheduled.get('asOf'),
            'source': 'scheduled',
        }

    @classmethod
    async def refresh_board_quotes_cache(cls, query_db: AsyncSession) -> dict[str, Any]:
        """
        jobs 专用：扫描 Influx 最新两根日K，写入 Redis。请求线程禁止调用。
        """
        from module_market.entity.vo.market_vo import (  # noqa: PLC0415 - jobs 专用路径按需加载
            MarketInstrumentQueryModel,
        )

        instruments = await cls.get_instrument_list_services(query_db, MarketInstrumentQueryModel())
        by_market: dict[str, list[str]] = {}
        for item in instruments:
            sym = str(item.get('symbol') or '').strip()
            if not sym:
                continue
            mkt = str(item.get('market') or 'US').strip().upper() or 'US'
            by_market.setdefault(mkt, []).append(sym)

        loop = asyncio.get_running_loop()
        bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for mkt, symbols in by_market.items():
            try:
                grouped = await loop.run_in_executor(None, InfluxUtil.query_latest_klines, mkt, symbols, 2, '-60d')
            except Exception as exc:
                # 看板是页面主路径：库故障降级为无行情并记录，不让整页 500
                logger.error(f'[看板] 行情批量查询失败 market={mkt}: {exc}')
                grouped = {}
            bars_by_symbol.update(grouped or {})

        quotes: list[dict[str, Any]] = []
        for item in instruments:
            sym = item.get('symbol')
            mkt = (item.get('market') or 'US').upper()
            bars = bars_by_symbol.get(sym) or []
            quote = cls._build_quote_from_klines(bars)
            source = 'influx' if quote else 'none'
            last = quote.get('last')
            change_rate = quote.get('changeRate')
            quotes.append(
                {
                    'symbol': sym,
                    'name': item.get('name'),
                    'market': mkt,
                    'category': item.get('category'),
                    'price': last,
                    'open': quote.get('open'),
                    'high': quote.get('high'),
                    'low': quote.get('low'),
                    'volume': quote.get('volume'),
                    'change': quote.get('change'),
                    'changeRate': change_rate,
                    'prevClose': quote.get('prevClose'),
                    'tradeDate': quote.get('tradeDate'),
                    'changeText': (
                        f"{'+' if change_rate >= 0 else ''}{change_rate:.2f}%"
                        if isinstance(change_rate, (int, float))
                        else '--'
                    ),
                    'up': True if change_rate is None else change_rate >= 0,
                    'source': source,
                    'bars': len(bars),
                }
            )

        indices = [q for q in quotes if q.get('category') == 'index' or str(q.get('symbol') or '').startswith('^')]
        index_symbols = {q['symbol'] for q in indices}
        rows = [q for q in quotes if q['symbol'] not in index_symbols]
        payload = {
            'quotes': quotes,
            'indices': indices,
            'rows': rows,
            'source': 'cache',
            'count': len(quotes),
            'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            'stale': False,
        }
        await cache_set_json(BOARD_QUOTES_CACHE_KEY, payload, BOARD_QUOTES_TTL_SECONDS)
        return {'count': len(quotes), 'asOf': payload['asOf']}

    @classmethod
    async def get_kline_services(cls, query_object: KlineQueryModel) -> list[dict[str, Any]]:
        """
        查询K线service（Influx为同步IO，放线程池执行）。
        daily/weekly/monthly 来自 daily_kline（周/月为真实日K聚合）；
        分钟级只读 minute_kline，没有则空列表，不补造。
        """
        loop = asyncio.get_running_loop()
        period = normalize_kline_period(query_object.period)
        start = default_range_start(period, query_object.start)
        if is_minute_period(period):
            klines = await loop.run_in_executor(
                None,
                InfluxUtil.query_minute_klines,
                query_object.market,
                query_object.symbol,
                start,
                query_object.stop,
            )
            how = {'5min': '5min', '15min': '15min'}.get(period)
            if how and klines:
                klines = cls._resample_minute_bars(klines, how)
            return klines
        klines = await loop.run_in_executor(
            None,
            InfluxUtil.query_klines,
            query_object.market,
            query_object.symbol,
            start,
            query_object.stop,
        )
        how = resample_how(period) or 'D'
        return _resample_klines(klines, how)

    @staticmethod
    def _resample_minute_bars(klines: list[dict[str, Any]], how: str) -> list[dict[str, Any]]:
        """把 1 分钟真实 bar 聚合成 5/15 分钟，不补空档。"""
        if not klines or how not in {'5min', '15min'}:
            return klines
        try:
            import pandas as pd  # noqa: PLC0415 - pandas 为可选重依赖，缺失时跳过重采样
        except Exception:
            return klines
        df = pd.DataFrame(klines)
        if df.empty or 'date' not in df.columns:
            return klines
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        rule = '5min' if how == '5min' else '15min'
        agg = (
            df.resample(rule)
            .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
            .dropna(subset=['open', 'close'])
        )
        out: list[dict[str, Any]] = []
        for idx, row in agg.iterrows():
            out.append(
                {
                    'date': idx.strftime('%Y-%m-%d %H:%M'),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row.get('volume') or 0),
                }
            )
        return out

    # ---------- 技术指标 ----------

    @classmethod
    async def get_indicators_services(cls, query_object: IndicatorQueryModel) -> dict[str, Any]:
        """
        计算全部技术指标service。
        """
        loop = asyncio.get_running_loop()
        klines = await loop.run_in_executor(
            None,
            InfluxUtil.query_klines,
            query_object.market,
            query_object.symbol,
            query_object.start,
            query_object.stop,
        )
        if not klines:
            return {'symbol': query_object.symbol, 'market': query_object.market, 'dates': []}
        indicators = await loop.run_in_executor(None, IndicatorService.calculate, klines)
        indicators['symbol'] = query_object.symbol
        indicators['market'] = query_object.market
        return indicators

    # ---------- 同步 ----------

    @classmethod
    async def sync_services(cls, sync_object: MarketSyncModel) -> dict[str, Any]:
        """
        手动触发同步service（同步IO放线程池执行，避免阻塞事件循环）。
        正式链路：外网/存量补源 → 直接写 Influx，无 MySQL 中间层。
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, MarketSyncService.sync, sync_object.symbol, sync_object.years
        )
        return result

    @classmethod
    async def migrate_mysql_to_influx_services(
        cls, symbol: str | None = None, market: str = 'US'
    ) -> dict[str, Any]:
        """
        将本库 MySQL 历史日K一次性迁入 Influx（可选，仅存量迁移）。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, MarketSyncService.mysql_to_influx, symbol, market
        )

    # ---------- AI分析 ----------

    @classmethod
    def _flatten_pick_analysis(cls, data: dict[str, Any]) -> dict[str, Any]:
        """把智能选股研判字段映射为行情 AI 接口的扁平响应（兼容旧字段）。"""
        recommendation = data.get('recommendation') or '观望'
        confidence = data.get('confidence')
        stance = data.get('stance')
        return {
            'ok': data.get('ok', False),
            'available': data.get('available', False),
            'symbol': data.get('symbol'),
            'market': data.get('market'),
            'name': data.get('name'),
            'modelName': data.get('modelName'),
            'klineCount': data.get('klineCount'),
            'price': data.get('price'),
            'changePct': data.get('changePct'),
            'factorScore': data.get('factorScore'),
            'pickScore': data.get('pickScore'),
            'signal': data.get('signal'),
            'recommendation': recommendation,
            'stance': stance,
            'confidence': confidence,
            'summary': data.get('summary'),
            'indicatorReview': data.get('indicatorReview'),
            'sentimentReview': data.get('sentimentReview'),
            'operationAdvice': data.get('operationAdvice'),
            'riskWarning': data.get('riskWarning'),
            'tags': data.get('tags') or [],
            'source': data.get('source'),
            'metrics': data.get('metrics') or {},
            'finalDecision': recommendation,
            'finalConfidence': confidence,
            'trend': stance,
            'advice': data.get('operationAdvice'),
            'message': data.get('message'),
            'aiOk': data.get('aiOk'),
            'aiError': data.get('aiError'),
        }

    @classmethod
    async def _persist_symbol_ai_analysis(
        cls, query_db: AsyncSession, data: dict[str, Any]
    ) -> None:
        if not data.get('ok'):
            return
        try:
            await SymbolAiAnalysisDao.add(
                query_db,
                {
                    'symbol': str(data.get('symbol') or '').strip().upper(),
                    'market': str(data.get('market') or 'US').upper(),
                    'price': float(data['price']) if data.get('price') is not None else None,
                    'final_decision': data.get('recommendation') or data.get('finalDecision'),
                    'final_confidence': data.get('confidence') or data.get('finalConfidence'),
                    'summary_text': data.get('summary') or '',
                    'indicators_json': json.dumps(data.get('metrics') or {}, ensure_ascii=False, default=str)[:60000],
                    'raw_json': json.dumps(
                        {
                            'recommendation': data.get('recommendation'),
                            'stance': data.get('stance'),
                            'confidence': data.get('confidence'),
                            'summary': data.get('summary'),
                            'indicatorReview': data.get('indicatorReview'),
                            'sentimentReview': data.get('sentimentReview'),
                            'operationAdvice': data.get('operationAdvice'),
                            'riskWarning': data.get('riskWarning'),
                            'pickScore': data.get('pickScore'),
                            'factorScore': data.get('factorScore'),
                            'signal': data.get('signal'),
                            'source': data.get('source'),
                        },
                        ensure_ascii=False,
                        default=str,
                    )[:60000],
                    'model_name': data.get('modelName'),
                    'analysis_time': datetime.now(),
                },
            )
            await query_db.commit()
        except Exception as exc:
            await query_db.rollback()
            logger.warning(f'[行情AI] 落库失败: {exc}')

    @classmethod
    async def ai_analyze_services(
        cls, query_db: AsyncSession, analyze_object: MarketAiAnalyzeModel
    ) -> dict[str, Any]:
        """
        对某标的做 AI 行情分析：复用智能选股同一套打分与 Grok 4.6 研判，结果落库 symbol_ai_analysis。
        """
        analyzed = await StockPickService.analyze_symbol(
            query_db,
            analyze_object.symbol,
            analyze_object.market or 'US',
            use_ai=True,
        )
        if not analyzed.get('ok'):
            return cls._flatten_pick_analysis(analyzed)

        flat = cls._flatten_pick_analysis(analyzed)
        await cls._persist_symbol_ai_analysis(query_db, flat)
        flat['result'] = {
            'recommendation': flat.get('recommendation'),
            'stance': flat.get('stance'),
            'confidence': flat.get('confidence'),
            'summary': flat.get('summary'),
            'indicator_review': flat.get('indicatorReview'),
            'sentiment_review': flat.get('sentimentReview'),
            'operation_advice': flat.get('operationAdvice'),
            'risk_warning': flat.get('riskWarning'),
            'pick_score': flat.get('pickScore'),
            'factor_score': flat.get('factorScore'),
            'signal': flat.get('signal'),
            'source': flat.get('source'),
        }
        return flat

    @classmethod
    async def ai_analyze_stream_services(
        cls, query_db: AsyncSession, analyze_object: MarketAiAnalyzeModel
    ) -> AsyncIterator[str] | Any:
        """
        行情 AI 分析流式传输：后台走智能选股研判，向前端输出格式化文本。
        """
        yield '正在加载 K 线与市场环境…\n'
        analyzed = await StockPickService.analyze_symbol(
            query_db,
            analyze_object.symbol,
            analyze_object.market or 'US',
            use_ai=True,
        )
        if not analyzed.get('ok'):
            yield json.dumps({'error': analyzed.get('message') or '分析失败'}, ensure_ascii=False)
            return

        flat = cls._flatten_pick_analysis(analyzed)
        await cls._persist_symbol_ai_analysis(query_db, flat)
        sections = [
            ('建议', f'{flat.get("recommendation")} · {flat.get("stance")} · 置信度 {flat.get("confidence")}'),
            ('综合', flat.get('summary')),
            ('指标', flat.get('indicatorReview')),
            ('舆情', flat.get('sentimentReview')),
            ('操作', flat.get('operationAdvice')),
            ('风险', flat.get('riskWarning')),
        ]
        for title, body in sections:
            if body:
                yield f'\n【{title}】\n{body}\n'
        yield '\n[完成]\n'

    @classmethod
    async def get_latest_ai_analysis(
        cls, query_db: AsyncSession, symbol: str, market: str = 'US'
    ) -> dict[str, Any] | None:
        row = await SymbolAiAnalysisDao.get_latest(query_db, symbol.strip().upper(), market.upper())
        if not row:
            return None
        raw = {}
        try:
            raw = json.loads(row.raw_json) if row.raw_json else {}
        except Exception:
            raw = {}
        recommendation = raw.get('recommendation') or row.final_decision
        confidence = raw.get('confidence') if raw.get('confidence') is not None else row.final_confidence
        stance = raw.get('stance')
        return {
            'analysisId': row.analysis_id,
            'symbol': row.symbol,
            'market': row.market,
            'price': row.price,
            'recommendation': recommendation,
            'stance': stance,
            'confidence': confidence,
            'finalDecision': recommendation,
            'finalConfidence': confidence,
            'trend': stance,
            'summary': row.summary_text,
            'summaryText': row.summary_text,
            'indicatorReview': raw.get('indicatorReview'),
            'sentimentReview': raw.get('sentimentReview'),
            'operationAdvice': raw.get('operationAdvice'),
            'riskWarning': raw.get('riskWarning'),
            'pickScore': raw.get('pickScore'),
            'factorScore': raw.get('factorScore'),
            'signal': raw.get('signal'),
            'source': raw.get('source'),
            'metrics': json.loads(row.indicators_json) if row.indicators_json else {},
            'indicators': json.loads(row.indicators_json) if row.indicators_json else {},
            'raw': raw,
            'modelName': row.model_name,
            'analysisTime': row.analysis_time.strftime('%Y-%m-%d %H:%M:%S') if row.analysis_time else None,
            'advice': raw.get('operationAdvice'),
        }

    # ---------- 标的详情 overview ----------

    @classmethod
    async def get_symbol_overview_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        include: str = 'core',
        history_limit: int = 120,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        include = (include or 'core').strip().lower()
        history_limit = max(20, min(int(history_limit or 120), 500))

        instrument = await MarketInstrumentDao.get_by_symbol(query_db, symbol)
        meta = get_instrument_meta(symbol)
        name = (instrument.name if instrument else None) or (meta[1] if meta else symbol)
        category = (instrument.category if instrument else None) or (meta[3] if meta else None)

        loop = asyncio.get_running_loop()
        klines = await loop.run_in_executor(
            None, InfluxUtil.query_klines, market, symbol, '-1y', 'now()', history_limit
        )
        snapshot = await loop.run_in_executor(None, IndicatorService.latest_snapshot, klines) if klines else {}
        quote = cls._build_quote_from_klines(klines)

        # Browse/history path: quote from Influx klines only — do not overlay Longbridge realtime/static_info.
        price_source = 'history'

        fundamentals = {
            'symbol': symbol,
            'name': name,
            'market': market,
            'category': category,
        }

        tech_card = cls._tech_card_from_snapshot(snapshot)

        latest_ai = await cls.get_latest_ai_analysis(query_db, symbol, market)
        latest_trend = await QuantStrategyDao.get_latest_signal_for_symbol(query_db, symbol, user_id=user_id)

        core = {
            'symbol': symbol,
            'market': market,
            'name': name,
            'fundamentals': fundamentals,
            'quote': {**quote, 'source': price_source},
            'techSnapshot': tech_card,
            'latestAiAnalysis': latest_ai,
            'latestTrendScan': cls._map_signal_to_trend(latest_trend),
            'meta': {
                'include': 'core',
                'priceSource': price_source,
                'snapshotAt': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            },
        }
        if include != 'all':
            return core

        # all：补全历史K线、市场简报、内容缓存
        history_items = klines[-history_limit:] if klines else []
        market_insight = None
        market_scan = None
        try:
            briefings = await FinanceNewsService.get_briefings(query_db, limit=20, market=market, refresh=False)
            for b in briefings.get('data') or []:
                if b.get('briefingType') == 'market-insight' and not market_insight:
                    market_insight = b
                if b.get('briefingType') == 'market-ai-scan' and not market_scan:
                    market_scan = b
        except Exception as e:
            logger.warning(f'[overview] 简报加载失败: {e}')

        content_cache = {'announcement': [], 'news': [], 'topic': []}
        for ctype in content_cache:
            try:
                pack = await SymbolContentService.get_content(
                    query_db, symbol, market, content_type=ctype, limit=8, refresh=False
                )
                content_cache[ctype] = pack.get('items') or []
            except Exception as e:  # noqa: PERF203 - 单内容类型失败不中断其余
                logger.warning(f'[overview] 内容缓存 {ctype} 失败: {e}')

        core.update(
            {
                'history': {
                    'items': history_items,
                    'summary': {
                        'count': len(history_items),
                        'start': history_items[0].get('date') if history_items else None,
                        'end': history_items[-1].get('date') if history_items else None,
                    },
                },
                'marketInsight': market_insight,
                'marketScan': market_scan,
                'contentCache': content_cache,
                'meta': {
                    'include': 'all',
                    'priceSource': price_source,
                    'snapshotAt': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
                },
            }
        )
        return core

    @classmethod
    def _build_quote_from_klines(cls, klines: list[dict[str, Any]]) -> dict[str, Any]:
        # 统一走公共实现，与 trade 侧保持一致
        return build_quote_from_klines(klines)

    @classmethod
    def _tech_card_from_snapshot(cls, snap: dict[str, Any]) -> dict[str, Any]:
        if not snap:
            return {}
        rsi = (snap.get('rsi') or {}).get('rsi12') or (snap.get('rsi') or {}).get('rsi6')
        macd_hist = (snap.get('macd') or {}).get('macd')
        ma20 = (snap.get('ma') or {}).get('ma20')
        close = snap.get('close')
        trend_label = '中性'
        try:
            if close and ma20 and float(close) > float(ma20) and macd_hist is not None and float(macd_hist) > 0:
                trend_label = '偏多'
            elif close and ma20 and float(close) < float(ma20) and macd_hist is not None and float(macd_hist) < 0:
                trend_label = '偏空'
            elif rsi is not None and float(rsi) > _RSI_OVERBOUGHT:
                trend_label = '超买'
            elif rsi is not None and float(rsi) < _RSI_OVERSOLD:
                trend_label = '超卖'
        except (TypeError, ValueError):
            pass
        boll = snap.get('boll') or {}
        return {
            'date': snap.get('date'),
            'trendLabel': trend_label,
            'rsi': rsi,
            'momentumScore': None,
            'supportPrice': boll.get('lower'),
            'resistancePrice': boll.get('upper'),
            'atr': snap.get('atr'),
            'ma20': ma20,
            'macdHist': macd_hist,
            'close': close,
            'raw': snap,
        }

    @classmethod
    def _map_signal_to_trend(cls, signal: Any) -> dict[str, Any] | None:
        if not signal:
            return None
        factor = {}
        try:
            factor = json.loads(signal.factor_json) if signal.factor_json else {}
        except Exception:
            factor = {}
        score = factor.get('score') or {}
        return {
            'symbol': signal.symbol,
            'trendDirection': score.get('trendDirection') or signal.signal,
            'technicalScore': signal.score,
            'confidence': signal.confidence,
            'riskLevel': score.get('riskLevel'),
            'headline': f'{signal.symbol} {signal.signal}',
            'summary': signal.reason,
            'indicators': factor.get('metrics') or {},
            'signal': signal.signal,
            'createTime': signal.create_time.strftime('%Y-%m-%d %H:%M:%S') if signal.create_time else None,
        }

    # ---------- 财经资讯 / 内容 ----------

    @classmethod
    async def get_finance_briefings_services(
        cls, query_db: AsyncSession, limit: int = 20, market: str | None = None, refresh: bool = False
    ) -> dict[str, Any]:
        return await FinanceNewsService.get_briefings(query_db, limit=limit, market=market, refresh=refresh)

    @classmethod
    async def get_symbol_content_services(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        content_type: str = 'news',
        limit: int = 20,
        refresh: bool = False,
    ) -> dict[str, Any]:
        return await SymbolContentService.get_content(
            query_db, symbol, market, content_type=content_type, limit=limit, refresh=refresh
        )
