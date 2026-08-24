"""长桥行情客户端：QuoteContext/ContentContext 与行情、盘口、K线、分时、资讯。"""

from __future__ import annotations

import asyncio
from typing import Any

from module_quant.service.longbridge.auth import (
    DEPTH_CACHE_TTL,
    QUOTE_CACHE_TTL,
    QUOTE_NEGATIVE_CACHE_TTL,
    TRADES_CACHE_TTL,
)
from module_quant.service.longbridge_quote import (
    CN_NO_DEPTH_MSG,
    assemble_depth,
    assemble_trades,
    empty_depth,
    empty_trades,
    is_cn_market,
    map_candlestick,
    map_intraday_point,
    overlay_last_bar,
    quote_error_message,
    quote_error_reason,
)
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.longbridge_breaker import LongbridgeBreaker


class QuoteClientMixin:
    """行情相关方法，由 LongbridgeService 组合继承。"""

    _cached_quote_ctxs: dict[str, Any] = {}
    _cached_content_ctxs: dict[str, Any] = {}

    @classmethod
    def _build_quote_context(cls) -> Any:
        """构建/复用 QuoteContext（延迟导入）。熔断开闸时不再建连。"""
        if cls._blocked():
            return None
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        cached = cls._cached_quote_ctxs.get(sig)
        if cached is not None:
            return cached

        config = cls._build_config()
        if config is None:
            return None
        from longport.openapi import QuoteContext  # 延迟导入，SDK 为可选依赖

        try:
            ctx = QuoteContext(config)
            cls._cached_quote_ctxs[sig] = ctx
            return ctx
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 构建QuoteContext失败: {exc}')
            return None

    @classmethod
    def _build_content_context(cls) -> Any:
        """构建/复用 ContentContext（延迟导入）。"""
        if cls._blocked():
            return None
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        cached = cls._cached_content_ctxs.get(sig)
        if cached is not None:
            return cached

        config = cls._build_config()
        if config is None:
            return None
        try:
            from longport.openapi import ContentContext  # 延迟导入，SDK 为可选依赖

            ctx = ContentContext(config)
            cls._cached_content_ctxs[sig] = ctx
            return ctx
        except Exception as exc:
            logger.warning(f'[长桥] ContentContext 不可用: {exc}')
            return None

    # ------------------------------------------------------------- 对外接口 ---

    @classmethod
    def test_connection(cls) -> dict[str, Any]:
        """
        连通性测试：返回是否配置凭据、能否建 context。凭据为空不抛异常。
        """
        creds = cls.resolve_credentials()
        if not (creds['app_key'] and creds['app_secret'] and creds['access_token']):
            return {'configured': False, 'connected': False, 'message': '长桥凭据未配置'}
        try:
            ctx = cls._build_quote_context()
            if ctx is None:
                return {'configured': True, 'connected': False, 'message': '凭据不完整，无法建立连接'}
            return {
                'configured': True,
                'connected': True,
                'source': creds['source'],
                'region': creds['region'],
                'message': '长桥连接正常',
            }
        except Exception as exc:
            logger.warning(f'[长桥] 连通性测试失败: {exc}')
            return {'configured': True, 'connected': False, 'source': creds['source'],
                    'region': creds['region'], 'message': f'连接失败: {exc}'}

    @classmethod
    def to_longbridge_symbol(cls, symbol: str, market: str = 'US') -> str:
        """
        内部代码转长桥代码。AAPL/US -> AAPL.US；已带后缀则原样返回。
        指数（^ 开头）长桥通常不支持，原样返回。
        """
        raw = (symbol or '').strip().upper()
        mkt = (market or 'US').strip().upper()
        if not raw:
            return raw
        if '.' in raw or raw.startswith('^'):
            return raw
        suffix = {'US': 'US', 'HK': 'HK', 'CN': 'SH'}.get(mkt, mkt)
        # A股简化：6 开头 SH，否则 SZ（启发式）
        if mkt == 'CN' and raw.isdigit():
            suffix = 'SH' if raw.startswith('6') else 'SZ'
        return f'{raw}.{suffix}'

    @classmethod
    def get_realtime_quote(cls, symbols: list[str] | str) -> dict[str, Any]:
        """
        获取实时行情。凭据为空返回 configured=False。

        :param symbols: 长桥标准代码列表，如 ['AAPL.US','700.HK']；单个字符串也会被包装成列表。
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = [s for s in (str(x).strip() for x in (symbols or [])) if s]
        if not symbols:
            return {'configured': cls.is_configured(), 'quotes': [], 'message': '标的列表为空'}
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'quotes': []}
        if cls._blocked():
            return {
                'configured': True,
                'quotes': [],
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
            }
        try:
            ctx = cls._build_quote_context()
            if ctx is None:
                return {
                    'configured': True,
                    'quotes': [],
                    'reason': 'unavailable',
                    'message': '长桥 QuoteContext 不可用',
                }
            raw = ctx.quote(symbols)
            quotes = []
            for q in raw or []:
                last = cls._to_float(getattr(q, 'last_done', None))
                prev_close = cls._to_float(getattr(q, 'prev_close', None))
                change = None
                change_rate = None
                if last is not None and prev_close not in (None, 0):
                    change = round(last - prev_close, 4)
                    change_rate = round(change / prev_close * 100, 4)
                quotes.append(
                    {
                        'symbol': getattr(q, 'symbol', None),
                        'lastDone': last,
                        'prevClose': prev_close,
                        'open': cls._to_float(getattr(q, 'open', None)),
                        'high': cls._to_float(getattr(q, 'high', None)),
                        'low': cls._to_float(getattr(q, 'low', None)),
                        'volume': cls._to_float(getattr(q, 'volume', None)),
                        'turnover': cls._to_float(getattr(q, 'turnover', None)),
                        'change': change,
                        'changeRate': change_rate,
                        'timestamp': str(getattr(q, 'timestamp', None) or ''),
                    }
                )
            LongbridgeBreaker.record_success()
            return {'configured': True, 'quotes': quotes}
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取实时行情失败: {exc}')
            return {
                'configured': True,
                'reason': quote_error_reason(exc),
                'message': f'获取行情失败: {exc}',
                'quotes': [],
            }

    @classmethod
    def get_static_info(cls, symbols: list[str]) -> dict[str, Any]:
        """获取静态基本面（名称/行业等），凭据缺失返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'items': []}
        if cls._blocked():
            return {
                'configured': True,
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
                'items': [],
            }
        try:
            ctx = cls._build_quote_context()
            if ctx is None:
                return {'configured': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'items': []}
            raw = ctx.static_info(symbols)
            items = [
                {
                    'symbol': getattr(info, 'symbol', None),
                    'name': getattr(info, 'name_cn', None) or getattr(info, 'name_en', None) or getattr(info, 'name', None),
                    'exchange': getattr(info, 'exchange', None),
                    'currency': getattr(info, 'currency', None),
                    'lotSize': getattr(info, 'lot_size', None),
                    'totalShares': cls._to_float(getattr(info, 'total_shares', None)),
                    'circulatingShares': cls._to_float(getattr(info, 'circulating_shares', None)),
                    'eps': cls._to_float(getattr(info, 'eps', None)),
                    'epsTtm': cls._to_float(getattr(info, 'eps_ttm', None)),
                    'bps': cls._to_float(getattr(info, 'bps', None)),
                    'dividendYield': cls._to_float(getattr(info, 'dividend_yield', None)),
                }
                for info in raw or []
            ]
            LongbridgeBreaker.record_success()
            return {'configured': True, 'items': items}
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取静态信息失败: {exc}')
            return {'configured': True, 'message': f'获取静态信息失败: {exc}', 'items': []}

    @classmethod
    def is_cn_market(cls, market: str | None, symbol: str | None = None) -> bool:
        return is_cn_market(market, symbol)

    @classmethod
    def get_depth(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        """
        买卖盘。A 股直接空盘口；凭据缺失/401 返回空列表 + 提示，不抛异常。
        使用 QuoteContext.depth(symbol)。
        """
        if is_cn_market(market, symbol):
            return empty_depth(symbol, market, configured=cls.is_configured(), reason='cn_no_depth', message=CN_NO_DEPTH_MSG)
        if not cls.is_configured():
            return empty_depth(symbol, market, configured=False, reason='unconfigured', message='长桥凭据未配置，盘口暂不可用')
        if cls._blocked():
            return empty_depth(
                symbol, market, configured=True, reason='circuit_open',
                message=LongbridgeBreaker.blocked_message(),
            )
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            ctx = cls._build_quote_context()
            if ctx is None or not hasattr(ctx, 'depth'):
                return empty_depth(
                    symbol, market, configured=True, reason='unavailable',
                    message='长桥 QuoteContext.depth 不可用', lb_symbol=lb_symbol,
                )
            data = assemble_depth(ctx.depth(lb_symbol), symbol, market, lb_symbol)
            LongbridgeBreaker.record_success()
            return data
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取盘口失败 {lb_symbol}: {exc}')
            return empty_depth(
                symbol, market, configured=True, reason=quote_error_reason(exc),
                message=quote_error_message(exc, '盘口暂不可用'), lb_symbol=lb_symbol,
            )

    @classmethod
    def get_trades(cls, symbol: str, market: str = 'US', count: int = 30) -> dict[str, Any]:
        """最近成交。使用 QuoteContext.trades(symbol, count)。A 股空列表。"""
        count = max(1, min(int(count or 30), 100))
        if is_cn_market(market, symbol):
            return empty_trades(symbol, market, configured=cls.is_configured(), reason='cn_no_depth', message=CN_NO_DEPTH_MSG)
        if not cls.is_configured():
            return empty_trades(symbol, market, configured=False, reason='unconfigured', message='长桥凭据未配置，成交明细暂不可用')
        if cls._blocked():
            return empty_trades(
                symbol, market, configured=True, reason='circuit_open',
                message=LongbridgeBreaker.blocked_message(),
            )
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            ctx = cls._build_quote_context()
            if ctx is None or not hasattr(ctx, 'trades'):
                return empty_trades(
                    symbol, market, configured=True, reason='unavailable',
                    message='长桥 QuoteContext.trades 不可用', lb_symbol=lb_symbol,
                )
            data = assemble_trades(ctx.trades(lb_symbol, count), symbol, market, lb_symbol, count)
            LongbridgeBreaker.record_success()
            return data
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取成交明细失败 {lb_symbol}: {exc}')
            return empty_trades(
                symbol, market, configured=True, reason=quote_error_reason(exc),
                message=quote_error_message(exc, '成交明细暂不可用'), lb_symbol=lb_symbol,
            )

    @classmethod
    def get_candlesticks(cls, symbol: str, market: str = 'US', period: str = '1min', count: int = 200) -> dict[str, Any]:
        """最近 N 根 K。使用 QuoteContext.candlesticks；无数据则空列表，不补造。"""
        count = max(1, min(int(count or 200), 1000))
        if is_cn_market(market, symbol):
            return {
                'configured': cls.is_configured(),
                'available': False,
                'reason': 'cn_no_depth',
                'message': 'A股K线请使用时序库',
                'symbol': symbol,
                'market': 'CN',
                'period': period,
                'klines': [],
            }
        if not cls.is_configured():
            return {
                'configured': False,
                'available': False,
                'reason': 'unconfigured',
                'message': '长桥凭据未配置',
                'symbol': symbol,
                'market': market,
                'period': period,
                'klines': [],
            }
        if cls._blocked():
            return {
                'configured': True,
                'available': False,
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
                'symbol': symbol,
                'market': market,
                'period': period,
                'klines': [],
            }
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            from longport.openapi import AdjustType  # 延迟导入，SDK 为可选依赖

            ctx = cls._build_quote_context()
            period_enum = cls._resolve_lb_period(period)
            if ctx is None or period_enum is None or not hasattr(ctx, 'candlesticks'):
                return {
                    'configured': True,
                    'available': False,
                    'reason': 'unavailable',
                    'message': '长桥 candlesticks 不可用或周期不支持',
                    'symbol': symbol,
                    'market': market,
                    'period': period,
                    'klines': [],
                }
            adjust = getattr(AdjustType, 'NoAdjust', None) or getattr(AdjustType, 'NO_ADJUST', None)
            raw = ctx.candlesticks(lb_symbol, period_enum, count, adjust)
            with_time = str(period).lower() not in {'daily', 'day', 'd', '1d', 'weekly', 'week', 'w', 'monthly', 'month'}
            klines = [map_candlestick(x, with_time=with_time) for x in (raw or [])]
            klines = [x for x in klines if x.get('close') is not None]
            klines.sort(key=lambda x: str(x.get('date') or ''))
            LongbridgeBreaker.record_success()
            return {
                'configured': True,
                'available': bool(klines),
                'symbol': symbol,
                'market': str(market or 'US').upper(),
                'lbSymbol': lb_symbol,
                'period': period,
                'klines': klines,
            }
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取K线失败 {lb_symbol} {period}: {exc}')
            return {
                'configured': True,
                'available': False,
                'reason': quote_error_reason(exc),
                'message': quote_error_message(exc, '长桥K线暂不可用'),
                'symbol': symbol,
                'market': market,
                'period': period,
                'klines': [],
            }

    @classmethod
    def get_intraday(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        """分时线。使用 QuoteContext.intraday；失败则空列表。"""
        if is_cn_market(market, symbol):
            return {
                'configured': cls.is_configured(),
                'available': False,
                'reason': 'cn_no_depth',
                'message': 'A股分时请使用时序库',
                'symbol': symbol,
                'market': 'CN',
                'period': 'intraday',
                'klines': [],
            }
        if not cls.is_configured():
            return {
                'configured': False,
                'available': False,
                'reason': 'unconfigured',
                'message': '长桥凭据未配置',
                'symbol': symbol,
                'market': market,
                'period': 'intraday',
                'klines': [],
            }
        if cls._blocked():
            return {
                'configured': True,
                'available': False,
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
                'symbol': symbol,
                'market': market,
                'period': 'intraday',
                'klines': [],
            }
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            ctx = cls._build_quote_context()
            if ctx is None or not hasattr(ctx, 'intraday'):
                return {
                    'configured': True,
                    'available': False,
                    'reason': 'unavailable',
                    'message': '长桥 intraday 不可用',
                    'symbol': symbol,
                    'market': market,
                    'period': 'intraday',
                    'klines': [],
                }
            raw = ctx.intraday(lb_symbol)
            klines = [map_intraday_point(x) for x in (raw or [])]
            klines = [x for x in klines if x.get('close') is not None]
            klines.sort(key=lambda x: str(x.get('date') or ''))
            LongbridgeBreaker.record_success()
            return {
                'configured': True,
                'available': bool(klines),
                'symbol': symbol,
                'market': str(market or 'US').upper(),
                'lbSymbol': lb_symbol,
                'period': 'intraday',
                'klines': klines,
            }
        except Exception as exc:
            cls._note_sdk_error(exc)
            logger.warning(f'[长桥] 获取分时失败 {lb_symbol}: {exc}')
            return {
                'configured': True,
                'available': False,
                'reason': quote_error_reason(exc),
                'message': quote_error_message(exc, '分时暂不可用'),
                'symbol': symbol,
                'market': market,
                'period': 'intraday',
                'klines': [],
            }

    @classmethod
    def _resolve_lb_period(cls, period: str) -> Any:
        from module_market.service.kline_period import normalize_kline_period

        key = normalize_kline_period(period)
        names = {
            '1min': ('Min_1', 'Minute_1', 'Min1'),
            '5min': ('Min_5', 'Minute_5', 'Min5'),
            '15min': ('Min_15', 'Minute_15', 'Min15'),
            'daily': ('Day', 'Day_1'),
            'weekly': ('Week', 'Week_1'),
            'monthly': ('Month', 'Month_1'),
        }.get(key) or ()
        try:
            from longport.openapi import Period  # 延迟导入，SDK 为可选依赖
        except Exception as exc:
            logger.debug(f'[长桥] longport Period 枚举不可用: {exc}')
            return None
        for name in names:
            if hasattr(Period, name):
                return getattr(Period, name)
        return None

    @classmethod
    def fetch_symbol_content(cls, lb_symbol: str, content_types: list[str]) -> dict[str, list[Any]]:
        """
        拉取公告/资讯/讨论。announcement 走 QuoteContext.filings；
        news/topic 走 ContentContext。
        """
        result: dict[str, list[Any]] = {t: [] for t in content_types}
        if not cls.is_configured() or cls._blocked():
            return result
        # filings
        if 'announcement' in content_types:
            try:
                ctx = cls._build_quote_context()
                if ctx is not None and hasattr(ctx, 'filings'):
                    result['announcement'] = list(ctx.filings(lb_symbol) or [])
            except Exception as exc:
                cls._note_sdk_error(exc)
                logger.warning(f'[长桥] filings 失败 {lb_symbol}: {exc}')
        # news / topics
        need_content = [t for t in content_types if t in ('news', 'topic')]
        if need_content:
            try:
                content_ctx = cls._build_content_context()
                if content_ctx is not None:
                    if 'news' in need_content and hasattr(content_ctx, 'news'):
                        result['news'] = list(content_ctx.news(lb_symbol) or [])
                    if 'topic' in need_content and hasattr(content_ctx, 'topics'):
                        result['topic'] = list(content_ctx.topics(lb_symbol) or [])
            except Exception as exc:
                cls._note_sdk_error(exc)
                logger.warning(f'[长桥] content 失败 {lb_symbol}: {exc}')
        return result

    overlay_last_bar = staticmethod(overlay_last_bar)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """把 SDK 返回的 Decimal/数值安全转 float。"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def normalize_symbols(cls, symbols: list[str] | str, market: str = 'US') -> list[str]:
        if isinstance(symbols, str):
            symbols = [symbols]
        out: list[str] = []
        for raw in symbols or []:
            text = str(raw or '').strip()
            if not text:
                continue
            out.append(cls.to_longbridge_symbol(text, market))
        return out

    @classmethod
    def extract_last_price(cls, quote_result: dict[str, Any], symbol: str | None = None) -> float:
        """从 get_realtime_quote 结果中取 lastDone。"""
        quotes = quote_result.get('quotes') or []
        if symbol:
            target = str(symbol).strip().upper()
            lb = cls.to_longbridge_symbol(target).upper()
            for q in quotes:
                q_sym = str(q.get('symbol') or '').upper()
                if q_sym in {target, lb}:
                    return float(q.get('lastDone') or 0)
        if quotes:
            return float(quotes[0].get('lastDone') or 0)
        return 0.0

    # ------------------------------------------------------------- 异步封装 ---

    @classmethod
    async def get_realtime_quote_async(  # noqa: PLR0912 - 缓存/负缓存/回退分支内聚，拆分会重复加锁
        cls, symbols: list[str] | str, market: str = 'US'
    ) -> dict[str, Any]:
        """
        实时报价：按 symbol 粒度缓存（不同组合可复用），空结果写短 TTL 负缓存防止穿透打爆券商限频。
        """
        normalized = cls.normalize_symbols(symbols, market)
        tag = cls._creds_cache_tag()
        merged: dict[str, Any] = {'configured': True, 'quotes': [], 'cached': False}
        missing: list[str] = []
        for sym in normalized:
            per = await cache_get_json(f'lb:quote:{tag}:{sym}')
            if per is not None:
                if per.get('quotes'):
                    merged['quotes'].extend(per['quotes'])
                    if per.get('cached'):
                        merged['cached'] = True
                # 空负缓存条目：视为未命中，继续走批量路径补一次
                elif not per.get('negative'):
                    pass
            else:
                missing.append(sym)
        if not missing:
            return merged

        cache_key = f'lb:quote:{tag}:batch:' + ','.join(sorted(missing))
        cached_batch = await cache_get_json(cache_key)
        if cached_batch is not None and cached_batch.get('quotes') is not None:
            merged['quotes'].extend(cached_batch['quotes'])
            merged['cached'] = True
            return merged
        if cls._blocked():
            return {
                'configured': True,
                'quotes': [],
                'reason': 'circuit_open',
                'message': LongbridgeBreaker.blocked_message(),
                'cached': False,
            }
        await cls._throttle()
        data = await asyncio.to_thread(cls.get_realtime_quote, missing)
        quotes = data.get('quotes') or []
        if quotes:
            await cache_set_json(cache_key, {'quotes': quotes}, QUOTE_CACHE_TTL)
            # 同步写入按 symbol 粒度缓存，供其他组合复用
            by_sym: dict[str, dict[str, Any]] = {}
            for q in quotes:
                sym = str(q.get('symbol') or '').upper()
                if sym:
                    by_sym.setdefault(sym, {'quotes': []})['quotes'].append(q)
            for sym, payload in by_sym.items():
                await cache_set_json(f'lb:quote:{tag}:{sym}', payload, QUOTE_CACHE_TTL)
            merged['quotes'].extend(quotes)
            return merged
        # 空结果：写短 TTL 负缓存，避免每次请求都穿透到 Longbridge
        negative = {'quotes': [], 'negative': True}
        await cache_set_json(cache_key, negative, QUOTE_NEGATIVE_CACHE_TTL)
        return data

    @classmethod
    async def get_depth_async(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        cache_key = f'lb:depth:{lb_symbol}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        if cls._blocked():
            cached = await cache_get_json(cache_key)
            if cached:
                cached['cached'] = True
                cached['reason'] = cached.get('reason') or 'circuit_open'
                return cached
            return empty_depth(
                symbol, market, configured=True, reason='circuit_open', message=LongbridgeBreaker.blocked_message()
            )
        await cls._throttle()
        data = await asyncio.to_thread(cls.get_depth, symbol, market)
        if data.get('reason') in {'cn_no_depth', 'unconfigured'} or data.get('asks') or data.get('bids'):
            await cache_set_json(cache_key, data, DEPTH_CACHE_TTL)
        return data

    @classmethod
    async def get_trades_async(cls, symbol: str, market: str = 'US', count: int = 30) -> dict[str, Any]:
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        cache_key = f'lb:trades:{lb_symbol}:{int(count or 30)}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        if cls._blocked():
            cached = await cache_get_json(cache_key)
            if cached:
                cached['cached'] = True
                cached['reason'] = cached.get('reason') or 'circuit_open'
                return cached
            return empty_trades(
                symbol, market, configured=True, reason='circuit_open', message=LongbridgeBreaker.blocked_message()
            )
        await cls._throttle()
        data = await asyncio.to_thread(cls.get_trades, symbol, market, count)
        if data.get('reason') in {'cn_no_depth', 'unconfigured'} or data.get('trades'):
            await cache_set_json(cache_key, data, TRADES_CACHE_TTL)
        return data

    @classmethod
    async def get_candlesticks_async(
        cls, symbol: str, market: str = 'US', period: str = '1min', count: int = 200
    ) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_candlesticks, symbol, market, period, count)

    @classmethod
    async def get_intraday_async(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_intraday, symbol, market)
