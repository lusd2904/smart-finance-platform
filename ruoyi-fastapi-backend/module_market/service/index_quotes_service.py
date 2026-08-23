"""
大盘指数实时行情：舆情大盘顶部指数条的数据源。

腾讯行情批量接口一次抓取五条指数；服务端按各时区精确判断盘中
（含午休时段），只返回正在交易的市场；并用行情自带的时间戳比对
当地日期，节假日在盘但无新行情时自动隐藏。Redis 缓存 30 秒。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from datetime import time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

from utils.http_fetch import fetch
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger

CACHE_KEY = 'market:index:quotes'
CACHE_TTL = 30

_SATURDAY_WEEKDAY = 5

_UA = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn',
}

# 各市场交易时段（当地时刻，左闭右开）；CN/HK 含午休拆分，US 全天一段
_SESSIONS: dict[str, list[tuple[dt_time, dt_time]]] = {
    'CN': [(dt_time(9, 30), dt_time(11, 30)), (dt_time(13, 0), dt_time(15, 0))],
    'HK': [(dt_time(9, 30), dt_time(12, 0)), (dt_time(13, 0), dt_time(16, 0))],
    'US': [(dt_time(9, 30), dt_time(16, 0))],
}

_INDEX_SPECS: list[dict[str, str]] = [
    {'code': 'usINX', 'name': '标普500', 'market': 'US'},
    {'code': 'usIXIC', 'name': '纳斯达克', 'market': 'US'},
    {'code': 'r_hkHSI', 'name': '恒生指数', 'market': 'HK'},
    {'code': 'r_hkHSTECH', 'name': '恒生科技', 'market': 'HK'},
    {'code': 'sh000001', 'name': '上证指数', 'market': 'CN'},
]

_MARKET_TZ = {'CN': 'Asia/Shanghai', 'HK': 'Asia/Hong_Kong', 'US': 'America/New_York'}

# 腾讯行情字段索引：3=现价 4=昨收 30=时间戳 31=涨跌额 32=涨跌幅
_IDX_LAST, _IDX_PREV, _IDX_TIME, _IDX_CHG, _IDX_CHGPCT = 3, 4, 30, 31, 32
_MIN_PARTS = 33


def _is_in_session(market: str, now_local: datetime) -> bool:
    """按市场时区判断当前是否处于交易时段（工作日 + 时段内）。"""
    if now_local.weekday() >= _SATURDAY_WEEKDAY:
        return False
    current = now_local.time()
    return any(start <= current < end for start, end in _SESSIONS[market])


def list_session_status(now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """三市场是否盘中。未开盘的市场选股时去掉实时指数，只用指标+舆情。"""
    out: dict[str, dict[str, Any]] = {}
    for market, tz_name in _MARKET_TZ.items():
        tz = ZoneInfo(tz_name)
        now_local = now.astimezone(tz) if now and now.tzinfo else datetime.now(tz)
        out[market] = {
            'market': market,
            'open': _is_in_session(market, now_local),
            'localTime': now_local.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': tz_name,
        }
    return out


def _parse_quote_time(raw: str) -> datetime | None:
    """兼容腾讯三种时间戳格式：美股 2026-08-21、港股 2026/08/21、A股 20260821161402。"""
    raw = (raw or '').strip()

    def _try(fmt: str) -> datetime | None:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            return None

    return next((dt for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y%m%d%H%M%S') if (dt := _try(fmt)) is not None), None)


def _to_float(value: Any) -> float | None:
    if value is None or value in {'', '-'}:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _fetch_tencent_batch(codes: list[str]) -> dict[str, dict[str, Any]]:
    url = f'https://qt.gtimg.cn/q={",".join(codes)}'
    text = fetch(url, timeout_s=10, headers=_UA, encoding='gbk', retries=1)
    quotes: dict[str, dict[str, Any]] = {}
    for m in re.finditer(r'v_(\w+)="([^"]*)"', text):
        parts = m.group(2).split('~')
        if len(parts) < _MIN_PARTS:
            continue
        quotes[m.group(1)] = {
            'name': parts[1],
            'last': _to_float(parts[_IDX_LAST]),
            'prevClose': _to_float(parts[_IDX_PREV]),
            'quoteTime': parts[_IDX_TIME],
            'changePct': _to_float(parts[_IDX_CHGPCT]),
        }
    return quotes


class MarketIndexService:
    """盘中大盘指数查询：谁在盘中显示谁，不开盘全空。"""

    @classmethod
    async def get_in_session_quotes(cls) -> dict[str, Any]:
        cached = await cache_get_json(CACHE_KEY)
        if isinstance(cached, dict):
            return {**cached, 'cached': True}
        items = await asyncio.to_thread(cls._fetch_items)
        payload = {'items': items, 'asOf': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        await cache_set_json(CACHE_KEY, payload, CACHE_TTL)
        return {**payload, 'cached': False}

    @classmethod
    def _fetch_items(cls) -> list[dict[str, Any]]:
        # 第一步：按各时区本地时间筛出正在盘中的指数
        live_specs: list[tuple[dict[str, str], datetime]] = []
        for spec in _INDEX_SPECS:
            now_local = datetime.now(ZoneInfo(_MARKET_TZ[spec['market']]))
            if _is_in_session(spec['market'], now_local):
                live_specs.append((spec, now_local))
        if not live_specs:
            return []
        # 第二步：一次批量请求全部在盘指数
        try:
            quotes = _fetch_tencent_batch([spec['code'] for spec, _ in live_specs])
        except Exception as exc:
            logger.warning(f'[index-quotes] 批量行情失败: {exc}')
            return []
        # 第三步：行情时间戳必须等于当地今天，否则视为节假日休市
        items: list[dict[str, Any]] = []
        for spec, now_local in live_specs:
            quote = quotes.get(spec['code'])
            if not quote:
                continue
            quote_dt = _parse_quote_time(str(quote.get('quoteTime') or ''))
            if quote_dt is None or quote_dt.date() != now_local.date():
                continue
            change_pct = quote.get('changePct')
            last, prev = quote.get('last'), quote.get('prevClose')
            if change_pct is None and last and prev:
                change_pct = round((last / prev - 1.0) * 100, 2)
            items.append(
                {
                    'market': spec['market'],
                    'symbol': spec['code'],
                    'name': quote.get('name') or spec['name'],
                    'last': last,
                    'prevClose': prev,
                    'changePct': change_pct,
                    'quoteTime': quote.get('quoteTime'),
                }
            )
        return items
