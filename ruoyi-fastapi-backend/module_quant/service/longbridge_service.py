"""
长桥（Longbridge / longport）接入服务。

设计要点：
- 所有 longport 导入均放在函数内部（延迟导入），凭据为空/SDK缺失时不崩溃。
- 凭据来源优先级：DB 表 quant_longbridge_config > LongbridgeConfig(env)。
- 通过环境变量把凭据交给官方 SDK 的 Config.from_apikey 构建 QuoteContext/TradeContext。
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

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

_QUOTE_CACHE_TTL = 15
_ACCOUNT_CACHE_TTL = 30
_DEPTH_CACHE_TTL = 3
_TRADES_CACHE_TTL = 3


def _resolve_region(region: str | None) -> str:
    """归一化区域，默认 cn。"""
    return (str(region or '').strip().lower()) or 'cn'


def _endpoints(region: str) -> dict[str, str]:
    """按区域返回长桥接入端点。cn 走 .cn 域名，其余走国际域名。"""
    if region == 'cn':
        return {
            'http_url': 'https://openapi.longbridge.cn',
            'quote_ws_url': 'wss://openapi-quote.longbridge.cn/v2',
            'trade_ws_url': 'wss://openapi-trade.longbridge.cn/v2',
        }
    return {
        'http_url': 'https://openapi.longbridge.com',
        'quote_ws_url': 'wss://openapi-quote.longbridge.com/v2',
        'trade_ws_url': 'wss://openapi-trade.longbridge.com/v2',
    }


class LongbridgeService:
    """
    长桥行情/交易封装。凭据缺失时所有方法返回 configured=False，不抛异常。
    """

    # 运行期凭据覆盖（由 service 层在读取 DB 后注入，避免此模块直接依赖 DB）
    _override_credentials: dict[str, str] | None = None
    _cached_creds_sig: str | None = None
    _cached_quote_ctx: Any = None
    _cached_trade_ctx: Any = None
    _cached_content_ctx: Any = None

    @classmethod
    def _clear_cached_contexts(cls) -> None:
        """清理已缓存的上下文对象"""
        cls._cached_quote_ctx = None
        cls._cached_trade_ctx = None
        cls._cached_content_ctx = None
        cls._cached_creds_sig = None

    @classmethod
    def set_credentials(cls, credentials: dict[str, str] | None) -> None:
        """
        设置来自 DB 的凭据覆盖（优先级高于 env）。传 None 清除覆盖。

        :param credentials: {'app_key','app_secret','access_token','region'}
        """
        if credentials and any(
            credentials.get(k) for k in ('app_key', 'app_secret', 'access_token')
        ):
            cls._override_credentials = credentials
        else:
            cls._override_credentials = None
        cls._clear_cached_contexts()

    @classmethod
    def resolve_credentials(cls) -> dict[str, str]:
        """
        解析当前生效凭据：DB覆盖 > env(LongbridgeConfig)。

        :return: {'app_key','app_secret','access_token','region','source'}
        """
        if cls._override_credentials:
            creds = cls._override_credentials
            return {
                'app_key': str(creds.get('app_key') or ''),
                'app_secret': str(creds.get('app_secret') or ''),
                'access_token': str(creds.get('access_token') or ''),
                'region': _resolve_region(creds.get('region')),
                'source': 'db',
            }
        # 回退到 env 配置
        try:
            from config.env import LongbridgeConfig

            return {
                'app_key': str(LongbridgeConfig.longport_app_key or ''),
                'app_secret': str(LongbridgeConfig.longport_app_secret or ''),
                'access_token': str(LongbridgeConfig.longport_access_token or ''),
                'region': _resolve_region(LongbridgeConfig.longport_region),
                'source': 'env',
            }
        except Exception as exc:  # pragma: no cover
            logger.warning(f'[长桥] 读取env凭据失败: {exc}')
            return {'app_key': '', 'app_secret': '', 'access_token': '', 'region': 'cn', 'source': 'none'}

    @classmethod
    def is_configured(cls) -> bool:
        """是否已配置有效凭据（三要素齐全）。"""
        creds = cls.resolve_credentials()
        return bool(creds['app_key'] and creds['app_secret'] and creds['access_token'])

    @classmethod
    def is_trading_enabled(cls) -> bool:
        """
        是否开启了实盘交易（下单/撤单开关）。
        硬开关由 LongbridgeConfig.longport_trading_enabled 控制，默认 False（模拟/只读）。
        """
        try:
            from config.env import LongbridgeConfig

            return bool(getattr(LongbridgeConfig, 'longport_trading_enabled', False))
        except Exception:
            return False

    @classmethod
    def _get_creds_signature(cls, creds: dict[str, str]) -> str:
        """计算凭证摘要用于缓存失效检测"""
        return f"{creds.get('app_key')}:{creds.get('app_secret')}:{creds.get('access_token')}:{creds.get('region')}"

    @classmethod
    def _build_config(cls) -> Any:
        """
        用当前凭据构建 longport 的 Config（延迟导入）。凭据不全返回 None。
        """
        creds = cls.resolve_credentials()
        if not (creds['app_key'] and creds['app_secret'] and creds['access_token']):
            return None
        region = creds['region']
        endpoints = _endpoints(region)
        # 通过环境变量与显式参数双保险
        os.environ['LONGPORT_APP_KEY'] = creds['app_key']
        os.environ['LONGPORT_APP_SECRET'] = creds['app_secret']
        os.environ['LONGPORT_ACCESS_TOKEN'] = creds['access_token']
        os.environ['LONGPORT_REGION'] = region
        # 默认中文内容（公告/资讯标题与正文）
        os.environ['LONGPORT_LANGUAGE'] = 'zh-CN'
        from longport.openapi import Config, Language  # 延迟导入

        return Config.from_apikey(
            app_key=creds['app_key'],
            app_secret=creds['app_secret'],
            access_token=creds['access_token'],
            http_url=endpoints['http_url'],
            quote_ws_url=endpoints['quote_ws_url'],
            trade_ws_url=endpoints['trade_ws_url'],
            language=Language.ZH_CN,
        )

    @classmethod
    def _build_quote_context(cls) -> Any:
        """构建/复用 QuoteContext（延迟导入）。"""
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        if cls._cached_quote_ctx is not None and cls._cached_creds_sig == sig:
            return cls._cached_quote_ctx

        config = cls._build_config()
        if config is None:
            return None
        from longport.openapi import QuoteContext

        try:
            cls._cached_quote_ctx = QuoteContext(config)
            cls._cached_creds_sig = sig
            return cls._cached_quote_ctx
        except Exception as exc:
            logger.warning(f'[长桥] 构建QuoteContext失败: {exc}')
            return None

    @classmethod
    def _build_trade_context(cls) -> Any:
        """构建/复用 TradeContext（延迟导入）。"""
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        if cls._cached_trade_ctx is not None and cls._cached_creds_sig == sig:
            return cls._cached_trade_ctx

        config = cls._build_config()
        if config is None:
            return None
        from longport.openapi import TradeContext

        try:
            cls._cached_trade_ctx = TradeContext(config)
            cls._cached_creds_sig = sig
            return cls._cached_trade_ctx
        except Exception as exc:
            logger.warning(f'[长桥] 构建TradeContext失败: {exc}')
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
    async def ensure_credentials_from_db(cls, query_db: Any) -> None:
        """
        从 quant_longbridge_config 注入凭据（DB 优先）。
        延迟导入 DAO 避免循环依赖。
        """
        try:
            from module_quant.dao.quant_dao import QuantLongbridgeConfigDao

            config = await QuantLongbridgeConfigDao.get_config(query_db)
            if config and (config.app_key or config.app_secret or config.access_token):
                cls.set_credentials(
                    {
                        'app_key': config.app_key,
                        'app_secret': config.app_secret,
                        'access_token': config.access_token,
                        'region': config.region,
                    }
                )
        except Exception as exc:
            logger.warning(f'[长桥] 从DB加载凭据失败: {exc}')

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
        try:
            ctx = cls._build_quote_context()
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
            return {'configured': True, 'quotes': quotes}
        except Exception as exc:
            logger.warning(f'[长桥] 获取实时行情失败: {exc}')
            return {'configured': True, 'message': f'获取行情失败: {exc}', 'quotes': []}

    @classmethod
    def get_static_info(cls, symbols: list[str]) -> dict[str, Any]:
        """获取静态基本面（名称/行业等），凭据缺失返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'items': []}
        try:
            ctx = cls._build_quote_context()
            raw = ctx.static_info(symbols)
            items = []
            for info in raw or []:
                items.append(
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
                )
            return {'configured': True, 'items': items}
        except Exception as exc:
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
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            ctx = cls._build_quote_context()
            if ctx is None or not hasattr(ctx, 'depth'):
                return empty_depth(
                    symbol, market, configured=True, reason='unavailable',
                    message='长桥 QuoteContext.depth 不可用', lb_symbol=lb_symbol,
                )
            return assemble_depth(ctx.depth(lb_symbol), symbol, market, lb_symbol)
        except Exception as exc:
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
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            ctx = cls._build_quote_context()
            if ctx is None or not hasattr(ctx, 'trades'):
                return empty_trades(
                    symbol, market, configured=True, reason='unavailable',
                    message='长桥 QuoteContext.trades 不可用', lb_symbol=lb_symbol,
                )
            return assemble_trades(ctx.trades(lb_symbol, count), symbol, market, lb_symbol, count)
        except Exception as exc:
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
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            from longport.openapi import AdjustType

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
            from longport.openapi import Period
        except Exception:
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
        if not cls.is_configured():
            return result
        # filings
        if 'announcement' in content_types:
            try:
                ctx = cls._build_quote_context()
                if ctx is not None and hasattr(ctx, 'filings'):
                    result['announcement'] = list(ctx.filings(lb_symbol) or [])
            except Exception as exc:
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
                logger.warning(f'[长桥] content 失败 {lb_symbol}: {exc}')
        return result

    @classmethod
    def _build_content_context(cls) -> Any:
        """构建/复用 ContentContext（延迟导入）。"""
        creds = cls.resolve_credentials()
        sig = cls._get_creds_signature(creds)
        if cls._cached_content_ctx is not None and cls._cached_creds_sig == sig:
            return cls._cached_content_ctx

        config = cls._build_config()
        if config is None:
            return None
        try:
            from longport.openapi import ContentContext

            cls._cached_content_ctx = ContentContext(config)
            cls._cached_creds_sig = sig
            return cls._cached_content_ctx
        except Exception as exc:
            logger.warning(f'[长桥] ContentContext 不可用: {exc}')
            return None

    @classmethod
    def get_account_balance(cls) -> dict[str, Any]:
        """获取账户资金。凭据为空返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'balances': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.account_balance()
            balances = []
            for b in raw or []:
                balances.append(
                    {
                        'currency': getattr(b, 'currency', None),
                        'totalCash': cls._to_float(getattr(b, 'total_cash', None)),
                        'availableCash': cls._to_float(getattr(b, 'available_cash', None)),
                        'netAssets': cls._to_float(getattr(b, 'net_assets', None)),
                        'maxFinanceAmount': cls._to_float(getattr(b, 'max_finance_amount', None)),
                    }
                )
            return {'configured': True, 'balances': balances}
        except Exception as exc:
            logger.warning(f'[长桥] 获取账户资金失败: {exc}')
            return {'configured': True, 'message': f'获取账户资金失败: {exc}', 'balances': []}

    @classmethod
    def get_positions(cls) -> dict[str, Any]:
        """获取持仓。凭据为空返回 configured=False。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'positions': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.stock_positions()
            positions = []
            channels = getattr(raw, 'channels', None) or []
            for channel in channels:
                for p in getattr(channel, 'positions', None) or []:
                    positions.append(
                        {
                            'symbol': getattr(p, 'symbol', None),
                            'symbolName': getattr(p, 'symbol_name', None),
                            'quantity': cls._to_float(getattr(p, 'quantity', None)),
                            'availableQuantity': cls._to_float(getattr(p, 'available_quantity', None)),
                            'costPrice': cls._to_float(getattr(p, 'cost_price', None)),
                            'currency': getattr(p, 'currency', None),
                        }
                    )
            return {'configured': True, 'positions': positions}
        except Exception as exc:
            logger.warning(f'[长桥] 获取持仓失败: {exc}')
            return {'configured': True, 'message': f'获取持仓失败: {exc}', 'positions': []}

    @classmethod
    def get_today_orders(cls) -> dict[str, Any]:
        """今日订单。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'orders': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.today_orders()
            orders = [cls._map_order(o) for o in (raw or [])]
            return {'configured': True, 'orders': orders}
        except Exception as exc:
            logger.warning(f'[长桥] 获取今日订单失败: {exc}')
            return {'configured': True, 'message': f'获取今日订单失败: {exc}', 'orders': []}

    @classmethod
    def get_history_orders(cls, limit: int = 50) -> dict[str, Any]:
        """历史订单（SDK 支持范围内）。"""
        if not cls.is_configured():
            return {'configured': False, 'message': '长桥凭据未配置', 'orders': []}
        try:
            ctx = cls._build_trade_context()
            raw = ctx.history_orders()
            orders = [cls._map_order(o) for o in (raw or [])][: max(1, min(limit, 200))]
            return {'configured': True, 'orders': orders}
        except Exception as exc:
            logger.warning(f'[长桥] 获取历史订单失败: {exc}')
            return {'configured': True, 'message': f'获取历史订单失败: {exc}', 'orders': []}

    @classmethod
    def submit_order(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'LO',
        price: float | None = None,
        time_in_force: str = 'Day',
        market: str = 'US',
    ) -> dict[str, Any]:
        """
        提交订单。side: buy/sell；order_type: LO/MO 等；未配置凭据或未开启交易开关时不真正下单。
        """
        if not cls.is_configured():
            return {'configured': False, 'ok': False, 'message': '长桥凭据未配置'}
        if not cls.is_trading_enabled():
            return {
                'configured': True,
                'ok': False,
                'message': '实盘交易未启用，当前为只读/模拟模式，请管理员在系统设置中开启后再试',
            }
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        try:
            from longport.openapi import OrderSide, OrderType, TimeInForceType

            side_enum = OrderSide.Buy if str(side).lower() in {'buy', 'b', '买', '买入'} else OrderSide.Sell
            ot = str(order_type or 'LO').upper()
            type_map = {
                'LO': OrderType.LO,
                'MO': OrderType.MO,
                'ELO': getattr(OrderType, 'ELO', OrderType.LO),
                'AO': getattr(OrderType, 'AO', OrderType.LO),
            }
            type_enum = type_map.get(ot, OrderType.LO)
            tif = TimeInForceType.Day if str(time_in_force).lower().startswith('d') else TimeInForceType.Day
            ctx = cls._build_trade_context()
            kwargs: dict[str, Any] = {
                'side': side_enum,
                'submitted_quantity': quantity,
                'time_in_force': tif,
                'symbol': lb_symbol,
                'order_type': type_enum,
            }
            if ot == 'LO' and price is not None:
                kwargs['submitted_price'] = price
            resp = ctx.submit_order(**kwargs)
            order_id = getattr(resp, 'order_id', None) or getattr(resp, 'orderId', None)
            return {'configured': True, 'ok': True, 'orderId': order_id, 'symbol': lb_symbol, 'message': '下单已提交'}
        except Exception as exc:
            logger.warning(f'[长桥] 下单失败: {exc}')
            return {'configured': True, 'ok': False, 'message': f'下单失败: {exc}'}

    @classmethod
    def cancel_order(cls, order_id: str) -> dict[str, Any]:
        """撤单。"""
        if not cls.is_configured():
            return {'configured': False, 'ok': False, 'message': '长桥凭据未配置'}
        if not cls.is_trading_enabled():
            return {
                'configured': True,
                'ok': False,
                'message': '实盘交易未启用，当前为只读/模拟模式，请管理员在系统设置中开启后再试',
            }
        try:
            ctx = cls._build_trade_context()
            ctx.cancel_order(order_id)
            return {'configured': True, 'ok': True, 'orderId': order_id, 'message': '撤单已提交'}
        except Exception as exc:
            logger.warning(f'[长桥] 撤单失败: {exc}')
            return {'configured': True, 'ok': False, 'message': f'撤单失败: {exc}'}

    @classmethod
    def _map_order(cls, o: Any) -> dict[str, Any]:
        return {
            'orderId': getattr(o, 'order_id', None) or getattr(o, 'orderId', None),
            'symbol': getattr(o, 'symbol', None),
            'stockName': getattr(o, 'stock_name', None) or getattr(o, 'symbol_name', None),
            'side': str(getattr(o, 'side', '') or ''),
            'status': str(getattr(o, 'status', '') or ''),
            'orderType': str(getattr(o, 'order_type', '') or ''),
            'quantity': cls._to_float(getattr(o, 'quantity', None) or getattr(o, 'submitted_quantity', None)),
            'price': cls._to_float(getattr(o, 'price', None) or getattr(o, 'submitted_price', None)),
            'executedQuantity': cls._to_float(getattr(o, 'executed_quantity', None)),
            'executedPrice': cls._to_float(getattr(o, 'executed_price', None)),
            'currency': getattr(o, 'currency', None),
            'submittedAt': str(getattr(o, 'submitted_at', '') or getattr(o, 'updated_at', '') or ''),
        }

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

    @classmethod
    def extract_order_id(cls, order_result: dict[str, Any]) -> str | None:
        if not order_result.get('ok'):
            return None
        data = order_result.get('data') if isinstance(order_result.get('data'), dict) else {}
        order_id = order_result.get('orderId') or (data or {}).get('order_id') or (data or {}).get('orderId')
        return str(order_id) if order_id else None

    @classmethod
    def flatten_account(cls, account_result: dict[str, Any]) -> dict[str, Any]:
        """把 {balances:[{totalCash, netAssets, ...}]} 压成前端常用扁平字段。"""
        balances = account_result.get('balances') or []
        first = balances[0] if balances else {}
        configured = bool(account_result.get('configured'))
        if not configured:
            return {
                'configured': False,
                'message': account_result.get('message') or '长桥凭据未配置',
                'currency': None,
                'totalCash': None,
                'availableCash': None,
                'netAssets': None,
                'balances': [],
            }
        return {
            'configured': True,
            'message': account_result.get('message'),
            'currency': first.get('currency') or 'USD',
            'totalCash': float(first.get('totalCash') or 0),
            'availableCash': float(first.get('availableCash') or first.get('totalCash') or 0),
            'netAssets': float(first.get('netAssets') or first.get('totalCash') or 0),
            'balances': balances,
        }

    @classmethod
    async def get_realtime_quote_async(cls, symbols: list[str] | str, market: str = 'US') -> dict[str, Any]:
        normalized = cls.normalize_symbols(symbols, market)
        cache_key = 'lb:quote:' + ','.join(sorted(normalized))
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        data = await asyncio.to_thread(cls.get_realtime_quote, normalized)
        if data.get('quotes'):
            await cache_set_json(cache_key, data, _QUOTE_CACHE_TTL)
        return data

    @classmethod
    async def get_account_balance_async(cls) -> dict[str, Any]:
        cache_key = 'lb:account'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        data = await asyncio.to_thread(cls.get_account_balance)
        if data.get('configured') and data.get('balances'):
            await cache_set_json(cache_key, data, _ACCOUNT_CACHE_TTL)
        return data

    @classmethod
    async def get_positions_async(cls) -> dict[str, Any]:
        cache_key = 'lb:positions'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        data = await asyncio.to_thread(cls.get_positions)
        if data.get('configured'):
            await cache_set_json(cache_key, data, _ACCOUNT_CACHE_TTL)
        return data

    @classmethod
    async def get_today_orders_async(cls) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_today_orders)

    @classmethod
    async def get_history_orders_async(cls, limit: int = 50) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_history_orders, limit)

    @classmethod
    async def submit_order_async(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = 'LO',
        price: float | None = None,
        time_in_force: str = 'Day',
        market: str = 'US',
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            cls.submit_order,
            symbol,
            side,
            quantity,
            order_type,
            price,
            time_in_force,
            market,
        )

    @classmethod
    async def cancel_order_async(cls, order_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(cls.cancel_order, order_id)

    @classmethod
    async def get_depth_async(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        cache_key = f'lb:depth:{lb_symbol}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        data = await asyncio.to_thread(cls.get_depth, symbol, market)
        if data.get('reason') in {'cn_no_depth', 'unconfigured'} or data.get('asks') or data.get('bids'):
            await cache_set_json(cache_key, data, _DEPTH_CACHE_TTL)
        return data

    @classmethod
    async def get_trades_async(cls, symbol: str, market: str = 'US', count: int = 30) -> dict[str, Any]:
        lb_symbol = cls.to_longbridge_symbol(symbol, market)
        cache_key = f'lb:trades:{lb_symbol}:{int(count or 30)}'
        cached = await cache_get_json(cache_key)
        if cached:
            cached['cached'] = True
            return cached
        data = await asyncio.to_thread(cls.get_trades, symbol, market, count)
        if data.get('reason') in {'cn_no_depth', 'unconfigured'} or data.get('trades'):
            await cache_set_json(cache_key, data, _TRADES_CACHE_TTL)
        return data

    @classmethod
    async def get_candlesticks_async(
        cls, symbol: str, market: str = 'US', period: str = '1min', count: int = 200
    ) -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_candlesticks, symbol, market, period, count)

    @classmethod
    async def get_intraday_async(cls, symbol: str, market: str = 'US') -> dict[str, Any]:
        return await asyncio.to_thread(cls.get_intraday, symbol, market)
