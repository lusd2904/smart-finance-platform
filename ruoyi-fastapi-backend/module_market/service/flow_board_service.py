"""A 股资金面 + 宏观日历：东财公开接口 + Nasdaq 日历。

对照 OpenBB / Gloomberg 的日历与板块热力，不引入 akshare（体积大、热路径易超时）。
全部走 jobs 外的短缓存；失败返回空列表，不 502。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from utils.http_fetch import HttpFetchError, fetch_json
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.time_format_util import now_beijing

CACHE_TTL_SECONDS = 90
SECTOR_LIMIT = 30
TRADE_DATE_LOOKBACK = 5
WEEKDAY_FRIDAY = 5
ZT_PRICE_SCALE = 1000
BJ = ZoneInfo('Asia/Shanghai')

_EM_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://data.eastmoney.com/',
    'Accept': 'application/json, text/plain, */*',
}
_NASDAQ_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://www.nasdaq.com/',
    'Accept': 'application/json, text/javascript, */*',
}

_SECTOR_FS = {
    'industry': 'm:90+t:2',
    'concept': 'm:90+t:3',
}


def _to_float(value: Any) -> float | None:
    if value is None or value in {'', '-', '--'}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _cn_trade_date_candidates(now: datetime | None = None) -> list[str]:
    """北京时间往前找最近几个交易日（跳过周末）。"""
    cursor = now or now_beijing()
    cursor = cursor.replace(tzinfo=BJ) if cursor.tzinfo is None else cursor.astimezone(BJ)
    out: list[str] = []
    day = cursor
    while len(out) < TRADE_DATE_LOOKBACK:
        if day.weekday() < WEEKDAY_FRIDAY:
            out.append(day.strftime('%Y-%m-%d'))
        day -= timedelta(days=1)
    return out


def parse_sector_payload(payload: Any, *, limit: int = SECTOR_LIMIT) -> list[dict[str, Any]]:
    data = (payload or {}).get('data') or {}
    rows = data.get('diff') or []
    if isinstance(rows, dict):
        rows = [rows[key] for key in sorted(rows, key=lambda item: int(item) if str(item).isdigit() else 0)]
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('f14') or '').strip()
        if not name:
            continue
        items.append(
            {
                'code': str(row.get('f12') or ''),
                'name': name,
                'last': _to_float(row.get('f2')),
                'changePct': _to_float(row.get('f3')),
                'netInflow': _to_float(row.get('f62')),
                'netInflowPct': _to_float(row.get('f184')),
                'leaderName': str(row.get('f204') or '').replace(' ', ''),
                'leaderCode': str(row.get('f205') or ''),
            }
        )
        if len(items) >= limit:
            break
    return items


def _zt_price(raw: Any) -> float | None:
    price = _to_float(raw)
    if price is None:
        return None
    if price >= ZT_PRICE_SCALE:
        return round(price / ZT_PRICE_SCALE, 3)
    return price


def parse_limit_up_payload(payload: Any, *, limit: int = 40) -> list[dict[str, Any]]:
    data = (payload or {}).get('data') or {}
    pool = data.get('pool') or []
    items: list[dict[str, Any]] = []
    for row in pool:
        if not isinstance(row, dict):
            continue
        code = str(row.get('c') or '').strip()
        if not code:
            continue
        extra = row.get('zttj') if isinstance(row.get('zttj'), dict) else {}
        items.append(
            {
                'symbol': code,
                'name': str(row.get('n') or ''),
                'last': _zt_price(row.get('p')),
                'changePct': _to_float(row.get('zdp')),
                'amount': _to_float(row.get('amount')),
                'boards': _to_int(row.get('lbc')) or _to_int(extra.get('days')),
                'industry': str(row.get('hybk') or ''),
                'firstSeal': str(row.get('fbt') or ''),
            }
        )
        if len(items) >= limit:
            break
    return items


def parse_lhb_payload(payload: Any, *, limit: int = 30) -> list[dict[str, Any]]:
    result = (payload or {}).get('result') or {}
    rows = result.get('data') or []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get('SECURITY_CODE') or '').strip()
        if not code:
            continue
        items.append(
            {
                'symbol': code,
                'name': str(row.get('SECURITY_NAME_ABBR') or ''),
                'tradeDate': str(row.get('TRADE_DATE') or '')[:10],
                'last': _to_float(row.get('CLOSE_PRICE')),
                'changePct': _to_float(row.get('CHANGE_RATE')),
                'netAmt': _to_float(row.get('BILLBOARD_NET_AMT')),
                'explain': str(row.get('EXPLAIN') or ''),
            }
        )
        if len(items) >= limit:
            break
    return items


def parse_nasdaq_events(payload: Any, *, limit: int = 40) -> list[dict[str, Any]]:
    data = (payload or {}).get('data') or {}
    rows = data.get('rows') or []
    items: list[dict[str, Any]] = []
    as_of = str(data.get('asOf') or '')
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('eventName') or row.get('event') or '').strip()
        if not name:
            continue
        items.append(
            {
                'kind': 'macro',
                'time': str(row.get('gmt') or row.get('time') or ''),
                'country': str(row.get('country') or ''),
                'title': name,
                'actual': str(row.get('actual') or ''),
                'consensus': str(row.get('consensus') or ''),
                'previous': str(row.get('previous') or ''),
                'asOf': as_of,
            }
        )
        if len(items) >= limit:
            break
    return items


def parse_nasdaq_earnings(payload: Any, *, limit: int = 30) -> list[dict[str, Any]]:
    data = (payload or {}).get('data') or {}
    rows = data.get('rows') or []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get('symbol') or row.get('ticker') or '').strip().upper()
        if not symbol:
            continue
        items.append(
            {
                'kind': 'earnings',
                'symbol': symbol,
                'name': str(row.get('name') or row.get('companyName') or ''),
                'time': str(row.get('time') or row.get('lastYearRptDt') or ''),
                'epsForecast': str(row.get('epsForecast') or row.get('consensusEPS') or ''),
                'eps': str(row.get('eps') or row.get('lastYearEPS') or ''),
                'marketCap': str(row.get('marketCap') or ''),
            }
        )
        if len(items) >= limit:
            break
    return items


def _get_json(url: str, headers: dict[str, str]) -> Any | None:
    try:
        return fetch_json(url, headers=headers, timeout_s=8, retries=2)
    except (HttpFetchError, ValueError, TypeError) as exc:
        logger.warning(f'[flow-board] 抓取失败 url={url[:120]} err={exc}')
        return None


def _sector_url(kind: str, limit: int) -> str:
    fs = _SECTOR_FS.get(kind, _SECTOR_FS['industry'])
    fields = 'f12,f14,f2,f3,f62,f184,f204,f205'
    return (
        'https://push2.eastmoney.com/api/qt/clist/get'
        f'?fid=f62&po=1&pz={limit}&pn=1&np=1&fltt=2&invt=2&fs={fs}'
        f'&fields={fields}'
    )


def _zt_url(yyyymmdd: str) -> str:
    return (
        'https://push2ex.eastmoney.com/getTopicZTPool'
        '?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt'
        f'&Pageindex=0&pagesize=50&sort=fbt:asc&date={yyyymmdd}'
    )


def _lhb_url(iso_date: str) -> str:
    filt = quote(f"(TRADE_DATE='{iso_date}')", safe="()='-")
    return (
        'https://datacenter-web.eastmoney.com/api/data/v1/get'
        '?reportName=RPT_DAILYBILLBOARD_DETAILSNEW'
        '&columns=SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,CLOSE_PRICE,CHANGE_RATE,BILLBOARD_NET_AMT,EXPLAIN'
        f'&filter={filt}&pageNumber=1&pageSize=30&sortTypes=-1&sortColumns=BILLBOARD_NET_AMT'
        '&source=WEB&client=WEB'
    )


class MarketFlowBoardService:
    """板块资金 / 涨停 / 龙虎榜 / 宏观与财报日历。"""

    @classmethod
    async def get_board_services(
        cls,
        *,
        sector_kind: str = 'industry',
        limit: int = 20,
    ) -> dict[str, Any]:
        kind = sector_kind if sector_kind in _SECTOR_FS else 'industry'
        cap = max(5, min(int(limit or 20), SECTOR_LIMIT))
        cache_key = f'market:flow:board:{kind}:{cap}'
        cached = await cache_get_json(cache_key)
        if isinstance(cached, dict) and cached.get('sectors') is not None:
            return cached

        dates = _cn_trade_date_candidates()
        us_date = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
        industry, concept, limit_up, lhb, macro, earnings = await asyncio.gather(
            asyncio.to_thread(cls._load_sectors, 'industry', cap),
            asyncio.to_thread(cls._load_sectors, 'concept', cap),
            asyncio.to_thread(cls._load_limit_up, dates),
            asyncio.to_thread(cls._load_lhb, dates),
            asyncio.to_thread(cls._load_macro, us_date),
            asyncio.to_thread(cls._load_earnings, us_date),
        )
        payload = {
            'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            'tradeDate': (limit_up.get('tradeDate') or lhb.get('tradeDate') or (dates[0] if dates else '')),
            'sectorKind': kind,
            'sectors': industry.get('items') if kind == 'industry' else concept.get('items'),
            'industry': industry.get('items') or [],
            'concept': concept.get('items') or [],
            'limitUp': limit_up.get('items') or [],
            'limitUpCount': limit_up.get('count') or len(limit_up.get('items') or []),
            'lhb': lhb.get('items') or [],
            'calendar': {
                'date': us_date,
                'macro': macro.get('items') or [],
                'earnings': earnings.get('items') or [],
            },
            'sources': {
                'sectors': 'eastmoney',
                'limitUp': 'eastmoney',
                'lhb': 'eastmoney',
                'calendar': 'nasdaq',
            },
            'stale': False,
        }
        if kind == 'concept':
            payload['sectors'] = concept.get('items') or []
        await cache_set_json(cache_key, payload, CACHE_TTL_SECONDS)
        return payload

    @classmethod
    def _load_sectors(cls, kind: str, limit: int) -> dict[str, Any]:
        payload = _get_json(_sector_url(kind, limit), _EM_HEADERS)
        items = parse_sector_payload(payload, limit=limit)
        return {'kind': kind, 'items': items}

    @classmethod
    def _load_limit_up(cls, dates: list[str]) -> dict[str, Any]:
        for iso in dates:
            ymd = iso.replace('-', '')
            payload = _get_json(_zt_url(ymd), _EM_HEADERS)
            items = parse_limit_up_payload(payload)
            count = _to_int(((payload or {}).get('data') or {}).get('tc')) if isinstance(payload, dict) else None
            if items:
                return {'tradeDate': iso, 'items': items, 'count': count or len(items)}
        return {'tradeDate': dates[0] if dates else '', 'items': [], 'count': 0}

    @classmethod
    def _load_lhb(cls, dates: list[str]) -> dict[str, Any]:
        for iso in dates:
            payload = _get_json(_lhb_url(iso), _EM_HEADERS)
            items = parse_lhb_payload(payload)
            if items:
                return {'tradeDate': iso, 'items': items}
        return {'tradeDate': dates[0] if dates else '', 'items': []}

    @classmethod
    def _load_macro(cls, iso_date: str) -> dict[str, Any]:
        url = f'https://api.nasdaq.com/api/calendar/economicevents?date={iso_date}'
        payload = _get_json(url, _NASDAQ_HEADERS)
        return {'items': parse_nasdaq_events(payload)}

    @classmethod
    def _load_earnings(cls, iso_date: str) -> dict[str, Any]:
        url = f'https://api.nasdaq.com/api/calendar/earnings?date={iso_date}'
        payload = _get_json(url, _NASDAQ_HEADERS)
        return {'items': parse_nasdaq_earnings(payload)}
