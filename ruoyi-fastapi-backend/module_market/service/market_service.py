"""
行情数据中心模块服务层：编排标的元数据、K线查询、指标计算、同步、AI分析、详情概览。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_ai.dao.ai_model_dao import AiModelDao
from module_market.constant.instruments import TARGET_INSTRUMENTS, get_instrument_meta
from module_market.dao.market_dao import MarketInstrumentDao, SymbolAiAnalysisDao
from module_market.entity.vo.market_vo import (
    IndicatorQueryModel,
    KlineQueryModel,
    MarketAiAnalyzeModel,
    MarketInstrumentModel,
    MarketInstrumentQueryModel,
    MarketSyncModel,
)
from module_market.service.content_cache_service import SymbolContentService
from module_market.service.finance_news_service import FinanceNewsService
from module_market.service.indicator_service import IndicatorService
from module_market.service.kline_period import default_range_start, is_minute_period, normalize_kline_period, resample_how
from module_market.service.market_analyzer_service import MarketAiAnalyzer
from module_market.service.sync_service import MarketSyncService
from module_market.service.tradingview_service import _resample_klines
from module_quant.dao.quant_dao import QuantStrategyDao
from module_quant.service.longbridge_service import LongbridgeService
from utils.common_util import CamelCaseUtil
from utils.crypto_util import CryptoUtil
from utils.influx_util import InfluxUtil
from utils.log_util import logger

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
    async def get_instrument_list_services(
        cls, query_db: AsyncSession, query_object: MarketInstrumentQueryModel
    ) -> list[dict[str, Any]]:
        """
        获取标的列表service（若表为空则先初始化目标标的）。
        """
        existing = await MarketInstrumentDao.get_all_symbols(query_db)
        if not existing:
            await cls.init_instruments_services(query_db)
        rows = await MarketInstrumentDao.get_instrument_list(query_db, query_object)
        return [
            MarketInstrumentModel(**CamelCaseUtil.transform_result(r)).model_dump(by_alias=True) for r in rows
        ]

    # ---------- K线 ----------

    @classmethod
    async def get_board_quotes_services(
        cls,
        query_db: AsyncSession,
        category: str | None = None,
        market: str | None = None,
    ) -> dict[str, Any]:
        """
        One-shot board quotes: latest 2 daily bars from Influx per symbol.
        Longbridge realtime overlay only when keys are present; otherwise Influx-only.
        """
        from module_market.entity.vo.market_vo import MarketInstrumentQueryModel

        instruments = await cls.get_instrument_list_services(
            query_db, MarketInstrumentQueryModel(category=category, market=market)
        )
        by_market: dict[str, list[str]] = {}
        meta_by_symbol: dict[str, dict[str, Any]] = {}
        for item in instruments:
            sym = str(item.get('symbol') or '').strip()
            if not sym:
                continue
            mkt = str(item.get('market') or 'US').strip().upper() or 'US'
            by_market.setdefault(mkt, []).append(sym)
            meta_by_symbol[sym] = item

        loop = asyncio.get_event_loop()
        bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for mkt, symbols in by_market.items():
            grouped = await loop.run_in_executor(None, InfluxUtil.query_latest_klines, mkt, symbols, 2, '-60d')
            bars_by_symbol.update(grouped or {})

        await LongbridgeService.ensure_credentials_from_db(query_db)
        lb_configured = LongbridgeService.is_configured()
        lb_quotes: dict[str, dict[str, Any]] = {}
        if lb_configured:
            lb_symbols = []
            for item in instruments:
                sym = str(item.get('symbol') or '')
                if not sym or sym.startswith('^'):
                    continue
                lb_symbols.append(LongbridgeService.to_longbridge_symbol(sym, item.get('market') or 'US'))
            if lb_symbols:
                rt = await loop.run_in_executor(None, LongbridgeService.get_realtime_quote, lb_symbols)
                for q in rt.get('quotes') or []:
                    raw = str(q.get('symbol') or '')
                    lb_quotes[raw.upper()] = q
                    if '.' in raw:
                        lb_quotes[raw.split('.', 1)[0].upper()] = q

        quotes: list[dict[str, Any]] = []
        for item in instruments:
            sym = item.get('symbol')
            mkt = (item.get('market') or 'US').upper()
            bars = bars_by_symbol.get(sym) or []
            quote = cls._build_quote_from_klines(bars)
            source = 'influx' if quote else 'none'
            if lb_configured and not str(sym).startswith('^'):
                lb_sym = LongbridgeService.to_longbridge_symbol(sym, mkt).upper()
                overlay = lb_quotes.get(lb_sym) or lb_quotes.get(str(sym).upper())
                if overlay:
                    quote = {
                        **quote,
                        'last': overlay.get('lastDone') if overlay.get('lastDone') is not None else quote.get('last'),
                        'open': overlay.get('open') if overlay.get('open') is not None else quote.get('open'),
                        'high': overlay.get('high') if overlay.get('high') is not None else quote.get('high'),
                        'low': overlay.get('low') if overlay.get('low') is not None else quote.get('low'),
                        'volume': overlay.get('volume') if overlay.get('volume') is not None else quote.get('volume'),
                        'change': overlay.get('change') if overlay.get('change') is not None else quote.get('change'),
                        'changeRate': overlay.get('changeRate')
                        if overlay.get('changeRate') is not None
                        else quote.get('changeRate'),
                        'prevClose': overlay.get('prevClose')
                        if overlay.get('prevClose') is not None
                        else quote.get('prevClose'),
                    }
                    source = 'longbridge'
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
        return {
            'quotes': quotes,
            'indices': indices,
            'rows': rows,
            'longbridgeConfigured': lb_configured,
            'source': 'longbridge' if lb_configured else 'influx',
            'count': len(quotes),
        }

    @classmethod
    async def get_kline_services(cls, query_object: KlineQueryModel) -> list[dict[str, Any]]:
        """
        查询K线service（Influx为同步IO，放线程池执行）。
        daily/weekly/monthly 来自 daily_kline（周/月为真实日K聚合）；
        分钟级只读 minute_kline，没有则空列表，不补造。
        """
        loop = asyncio.get_event_loop()
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
            import pandas as pd
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
        loop = asyncio.get_event_loop()
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
        loop = asyncio.get_event_loop()
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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, MarketSyncService.mysql_to_influx, symbol, market
        )

    # ---------- AI分析 ----------

    @classmethod
    def _map_decision(cls, result: dict[str, Any] | None) -> tuple[str, int, str]:
        """从模型 JSON 映射 final_decision / confidence / summary"""
        if not result:
            return '观望', 50, ''
        advice = str(result.get('operation_advice') or result.get('advice') or '')
        trend = str(result.get('trend') or '')
        text = advice + trend
        decision = '观望'
        if any(k in text for k in ('买入', '加仓', '做多', 'BUY', '买')):
            decision = '买入'
        elif any(k in text for k in ('卖出', '减仓', '做空', 'SELL', '卖')):
            decision = '卖出'
        elif '多头' in trend:
            decision = '买入'
        elif '空头' in trend:
            decision = '卖出'
        # 简易置信度：有支撑压力与摘要则 70，否则 55
        confidence = 70 if (result.get('support') or result.get('resistance')) else 55
        if trend == '震荡':
            confidence = 50
        summary = (
            result.get('trend_summary')
            or result.get('summary')
            or advice
            or result.get('indicator_review')
            or ''
        )
        return decision, confidence, str(summary)

    @classmethod
    async def ai_analyze_services(
        cls, query_db: AsyncSession, analyze_object: MarketAiAnalyzeModel
    ) -> dict[str, Any]:
        """
        对某标的做AI行情分析service：复用ai_models(scope='sentiment')的AI连接配置，
        取近N日K线+最新指标快照喂给模型，结果落库 symbol_ai_analysis。
        """
        base_url = api_key = model_name = None
        temperature = 0.2
        try:
            # 与舆情一致：sentiment -> global -> chat -> 任意可用模型
            ai_model = await AiModelDao.resolve_ai_model_for_business(query_db, 'sentiment')
            if ai_model:
                base_url = ai_model.base_url
                api_key = CryptoUtil.decrypt(ai_model.api_key) if ai_model.api_key else None
                model_name = ai_model.model_code
                if ai_model.temperature is not None:
                    temperature = ai_model.temperature
        except Exception as exc:
            logger.warning(f'[行情AI] 解析 AI 模型失败: {exc}')

        if not base_url or not api_key or not model_name:
            return {
                'ok': False,
                'available': False,
                'message': '未配置AI分析参数，请先在AI模型管理(scope=sentiment)或舆情AI配置中填写 Base URL / API Key / 模型',
                'result': None,
            }

        loop = asyncio.get_event_loop()
        klines = await loop.run_in_executor(
            None,
            InfluxUtil.query_klines,
            analyze_object.market,
            analyze_object.symbol,
            f'-{max(int(analyze_object.days or 120) + 80, 180)}d',
            'now()',
            400,
        )
        if not klines:
            return {
                'ok': False,
                'available': True,
                'message': f'标的 {analyze_object.symbol} 暂无K线数据，请先同步',
                'result': None,
            }

        recent = klines[-analyze_object.days :] if analyze_object.days > 0 else klines
        snapshot = await loop.run_in_executor(None, IndicatorService.latest_snapshot, klines)

        meta = get_instrument_meta(analyze_object.symbol)
        name = meta[1] if meta else analyze_object.symbol

        ai_result = await MarketAiAnalyzer.analyze(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            symbol=analyze_object.symbol,
            name=name,
            klines=recent,
            indicator_snapshot=snapshot,
            temperature=temperature,
        )

        parsed = ai_result.get('result') if ai_result.get('ok') else None
        decision, confidence, summary = cls._map_decision(parsed)
        price = snapshot.get('close') or (recent[-1].get('close') if recent else None)

        if ai_result.get('ok') and parsed:
            try:
                await SymbolAiAnalysisDao.add(
                    query_db,
                    {
                        'symbol': analyze_object.symbol.strip().upper(),
                        'market': (analyze_object.market or 'US').upper(),
                        'price': float(price) if price is not None else None,
                        'final_decision': decision,
                        'final_confidence': confidence,
                        'summary_text': summary,
                        'indicators_json': json.dumps(snapshot, ensure_ascii=False, default=str)[:60000],
                        'raw_json': json.dumps(parsed, ensure_ascii=False, default=str)[:60000],
                        'model_name': model_name,
                        'analysis_time': datetime.now(),
                    },
                )
                await query_db.commit()
            except Exception as e:
                await query_db.rollback()
                logger.warning(f'[行情AI] 落库失败: {e}')

        # 扁平字段便于前端直接展示
        flat = {}
        if parsed:
            flat = {
                'trend': parsed.get('trend'),
                'summary': summary,
                'trendSummary': parsed.get('trend_summary'),
                'support': parsed.get('support'),
                'resistance': parsed.get('resistance'),
                'indicatorReview': parsed.get('indicator_review'),
                'advice': parsed.get('operation_advice') or parsed.get('advice'),
                'operationAdvice': parsed.get('operation_advice'),
                'riskWarning': parsed.get('risk_warning'),
                'finalDecision': decision,
                'finalConfidence': confidence,
            }

        return {
            'ok': ai_result['ok'],
            'available': True,
            'symbol': analyze_object.symbol,
            'name': name,
            'modelName': model_name,
            'klineCount': len(recent),
            'price': price,
            'finalDecision': decision,
            'finalConfidence': confidence,
            'summary': summary,
            'result': {**(parsed or {}), **flat} if parsed else None,
            'message': '分析成功' if ai_result['ok'] else f'分析失败: {ai_result.get("error")}',
            **flat,
        }

    @classmethod
    async def ai_analyze_stream_services(
        cls, query_db: AsyncSession, analyze_object: MarketAiAnalyzeModel
    ):
        """
        行情AI分析流式传输生成器
        """
        base_url = api_key = model_name = None
        temperature = 0.2
        try:
            ai_model = await AiModelDao.resolve_ai_model_for_business(query_db, 'sentiment')
            if ai_model:
                base_url = ai_model.base_url
                api_key = CryptoUtil.decrypt(ai_model.api_key) if ai_model.api_key else None
                model_name = ai_model.model_code
                if ai_model.temperature is not None:
                    temperature = ai_model.temperature
        except Exception as exc:
            logger.warning(f'[行情AI流式] 解析 AI 模型失败: {exc}')

        if not base_url or not api_key or not model_name:
            yield json.dumps({'error': '未配置AI分析参数，请先在AI模型管理中配置'}, ensure_ascii=False)
            return

        klines = await asyncio.to_thread(
            InfluxUtil.query_klines,
            analyze_object.market,
            analyze_object.symbol,
            f'-{max(int(analyze_object.days or 120) + 80, 180)}d',
            'now()',
            400,
        )
        if not klines:
            yield json.dumps({'error': f'标的 {analyze_object.symbol} 暂无K线数据'}, ensure_ascii=False)
            return

        recent = klines[-analyze_object.days :] if analyze_object.days > 0 else klines
        snapshot = await asyncio.to_thread(IndicatorService.latest_snapshot, klines)
        meta = get_instrument_meta(analyze_object.symbol)
        name = meta[1] if meta else analyze_object.symbol

        async for chunk in MarketAiAnalyzer.analyze_stream(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            symbol=analyze_object.symbol,
            name=name,
            klines=recent,
            indicator_snapshot=snapshot,
            temperature=temperature,
        ):
            yield chunk

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
        return {
            'analysisId': row.analysis_id,
            'symbol': row.symbol,
            'market': row.market,
            'price': row.price,
            'finalDecision': row.final_decision,
            'finalConfidence': row.final_confidence,
            'summary': row.summary_text,
            'summaryText': row.summary_text,
            'indicators': json.loads(row.indicators_json) if row.indicators_json else {},
            'raw': raw,
            'modelName': row.model_name,
            'analysisTime': row.analysis_time.strftime('%Y-%m-%d %H:%M:%S') if row.analysis_time else None,
            'trend': raw.get('trend'),
            'advice': raw.get('operation_advice'),
            'support': raw.get('support'),
            'resistance': raw.get('resistance'),
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
    ) -> dict[str, Any]:
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        include = (include or 'core').strip().lower()
        history_limit = max(20, min(int(history_limit or 120), 500))

        instrument = await MarketInstrumentDao.get_by_symbol(query_db, symbol)
        meta = get_instrument_meta(symbol)
        name = (instrument.name if instrument else None) or (meta[1] if meta else symbol)
        category = (instrument.category if instrument else None) or (meta[3] if meta else None)

        loop = asyncio.get_event_loop()
        klines = await loop.run_in_executor(
            None, InfluxUtil.query_klines, market, symbol, '-1y', 'now()', history_limit
        )
        snapshot = await loop.run_in_executor(None, IndicatorService.latest_snapshot, klines) if klines else {}
        quote = cls._build_quote_from_klines(klines)

        # 长桥实时价覆盖（可选）
        price_source = 'history'
        await LongbridgeService.ensure_credentials_from_db(query_db)
        if LongbridgeService.is_configured() and not symbol.startswith('^'):
            lb_sym = LongbridgeService.to_longbridge_symbol(symbol, market)
            rt = await loop.run_in_executor(None, LongbridgeService.get_realtime_quote, [lb_sym])
            quotes = rt.get('quotes') or []
            if quotes:
                q0 = quotes[0]
                quote = {
                    **quote,
                    'last': q0.get('lastDone') or quote.get('last'),
                    'open': q0.get('open') or quote.get('open'),
                    'high': q0.get('high') or quote.get('high'),
                    'low': q0.get('low') or quote.get('low'),
                    'volume': q0.get('volume') or quote.get('volume'),
                    'change': q0.get('change'),
                    'changeRate': q0.get('changeRate'),
                    'prevClose': q0.get('prevClose'),
                }
                price_source = 'longbridge'

        fundamentals = {
            'symbol': symbol,
            'name': name,
            'market': market,
            'category': category,
        }
        if LongbridgeService.is_configured() and not symbol.startswith('^'):
            lb_sym = LongbridgeService.to_longbridge_symbol(symbol, market)
            static = await loop.run_in_executor(None, LongbridgeService.get_static_info, [lb_sym])
            items = static.get('items') or []
            if items:
                fundamentals.update({k: v for k, v in items[0].items() if v is not None})

        tech_card = cls._tech_card_from_snapshot(snapshot)

        latest_ai = await cls.get_latest_ai_analysis(query_db, symbol, market)
        latest_trend = await QuantStrategyDao.get_latest_signal_for_symbol(query_db, symbol)

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
                'snapshotAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
            except Exception as e:
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
                    'snapshotAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                },
            }
        )
        return core

    @classmethod
    def _build_quote_from_klines(cls, klines: list[dict[str, Any]]) -> dict[str, Any]:
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
            elif rsi is not None and float(rsi) > 70:
                trend_label = '超买'
            elif rsi is not None and float(rsi) < 30:
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
