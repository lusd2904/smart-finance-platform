"""
大盘指数实时行情：舆情大盘 / 行情热度 / 交易顶栏的数据源。

腾讯行情一次批量抓取三市场各三条指数（美股含道琼斯，港股含恒生国企，A 股含创业板/科创板）。
各市场始终返回最近一次有效报价，由客户端按当前市场筛选；Redis 缓存 30 秒。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from module_market.service.index_session import MARKET_TZ, is_in_session
from module_market.service.tencent_quote import fetch_tencent_batch, to_float
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.time_format_util import now_beijing

CACHE_KEY = 'market:index:quotes:v3'
CACHE_TTL = 30

_INDEX_SPECS: list[dict[str, str]] = [
    {'code': 'usINX', 'name': '标普500', 'market': 'US'},
    {'code': 'usIXIC', 'name': '纳斯达克', 'market': 'US'},
    {'code': 'usDJI', 'name': '道琼斯', 'market': 'US'},
    {'code': 'r_hkHSI', 'name': '恒生指数', 'market': 'HK'},
    {'code': 'r_hkHSTECH', 'name': '恒生科技', 'market': 'HK'},
    {'code': 'r_hkHSCEI', 'name': '恒生国企', 'market': 'HK'},
    {'code': 'sh000001', 'name': '上证指数', 'market': 'CN'},
    {'code': 'sz399006', 'name': '创业板指数', 'market': 'CN'},
    {'code': 'sh000688', 'name': '科创板指数', 'market': 'CN'},
]


def list_session_status(now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """三市场是否盘中。未开盘的市场选股时去掉实时指数，只用指标+舆情。"""
    out: dict[str, dict[str, Any]] = {}
    for market, tz_name in MARKET_TZ.items():
        tz = ZoneInfo(tz_name)
        now_local = now.astimezone(tz) if now and now.tzinfo else datetime.now(tz)
        out[market] = {
            'market': market,
            'open': is_in_session(market, now_local),
            'localTime': now_local.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': tz_name,
        }
    return out


class MarketIndexService:
    """大盘指数查询：美股全时段，港股 / A 股仅盘中。"""

    @classmethod
    async def get_in_session_quotes(cls) -> dict[str, Any]:
        cached = await cache_get_json(CACHE_KEY)
        if isinstance(cached, dict):
            return {**cached, 'cached': True}
        items = await asyncio.to_thread(cls._fetch_items)
        payload = {'items': items, 'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S')}
        await cache_set_json(CACHE_KEY, payload, CACHE_TTL)
        return {**payload, 'cached': False}

    @classmethod
    def _fetch_items(cls) -> list[dict[str, Any]]:
        try:
            quotes = fetch_tencent_batch([spec['code'] for spec in _INDEX_SPECS])
        except Exception as exc:
            logger.warning(f'[index-quotes] 批量行情失败: {exc}')
            return []
        items: list[dict[str, Any]] = []
        for spec in _INDEX_SPECS:
            quote = quotes.get(spec['code'])
            if not quote:
                continue
            last, prev = to_float(quote.get('last')), to_float(quote.get('prevClose'))
            if last is None:
                continue
            change_pct = quote.get('changePct')
            if change_pct is None and last and prev:
                change_pct = round((last / prev - 1.0) * 100, 2)
            items.append(
                {
                    'market': spec['market'],
                    'symbol': spec['code'],
                    'name': spec['name'],
                    'last': last,
                    'prevClose': prev,
                    'changePct': change_pct,
                    'quoteTime': quote.get('quoteTime'),
                }
            )
        return items
