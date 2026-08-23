"""
Multi-source real daily K-line fetchers.

Primary: Sina + Tencent
Fallbacks: East Money / Yahoo / Stooq / NetEase

Never invents OHLCV. Invalid or empty upstream payloads become [].
Each source has a process-local circuit breaker so a dying host is skipped.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import threading
import time
from datetime import date
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from module_market.constant.instruments import INDEX_SOURCE_MAP
from utils.log_util import logger

if TYPE_CHECKING:
    from collections.abc import Callable


# 解析器字段布局常量
_ISO_DATE_LEN, _MONTH_POS, _DAY_POS = 10, 4, 7
_TX_SERIES_MIN_FIELDS = 5
_EM_MIN_PARTS = 6
_NE_MIN_COLS = 5
_NE_CLOSE_COL = 3
_NE_HIGH_COL = 4
_NE_OPEN_COL = 6
_NE_VOL_COL = 11
_NE_TURNOVER_COL = 12

DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    ),
    'Accept': '*/*',
}

SINA_HEADERS = {
    **DEFAULT_HEADERS,
    'Referer': 'https://finance.sina.com.cn',
}

SINA_US_DAILY_URL = (
    'https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/'
    'var%20t=/US_MinKService.getDailyK'
)
SINA_CN_KLINE_URL = (
    'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'CN_MarketData.getKLineData'
)
SINA_HK_DAILY_URL = (
    'https://stock.finance.sina.com.cn/hkstock/api/jsonp_v2.php/'
    'var%20t=/HK_MinKService.getDailyK'
)
TENCENT_FQKLINE_URL = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
TENCENT_HK_FQKLINE_URL = 'https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get'
TENCENT_MINUTE_URLS = {
    'CN': 'http://web.ifzq.gtimg.cn/appstock/app/minute/query',
    'HK': 'http://web.ifzq.gtimg.cn/appstock/app/hkMinute/query',
    'US': 'http://web.ifzq.gtimg.cn/appstock/app/UsMinute/query',
}
EASTMONEY_KLINE_URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
YAHOO_CHART_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
STOOQ_CSV_URL = 'https://stooq.com/q/d/l/'
NETEASE_CHD_URL = 'https://quotes.money.163.com/service/chddata.html'

PRIMARY_SOURCES = ('sina', 'tencent')
FALLBACK_SOURCES = ('eastmoney', 'yahoo', 'stooq', 'netease')
ALL_SOURCES = PRIMARY_SOURCES + FALLBACK_SOURCES


def primary_sources_for(market: str) -> tuple[str, ...]:
    """港股新浪日K经常空，先腾讯；美股/A股仍先新浪。"""
    if (market or '').strip().upper() == 'HK':
        return ('tencent', 'sina')
    return PRIMARY_SOURCES
# 首源已有足够日K时不再打第二源/回退源，降低封禁概率
MIN_BARS_STOP = 40
DEFAULT_SOURCE_INTERVAL = float(os.environ.get('KLINE_SOURCE_INTERVAL', '0.8'))


class CircuitBreaker:
    """Skip a source after consecutive failures until cooldown elapses."""

    def __init__(self, fail_threshold: int = 3, cooldown_seconds: float = 180.0) -> None:
        self.fail_threshold = max(1, int(fail_threshold))
        self.cooldown_seconds = max(1.0, float(cooldown_seconds))
        self.failures = 0
        self.opened_until = 0.0

    def allow(self, now: float | None = None) -> bool:
        ts = time.time() if now is None else now
        if self.opened_until and ts < self.opened_until:
            return False
        if self.opened_until and ts >= self.opened_until:
            self.opened_until = 0.0
            self.failures = 0
        return True

    def record_success(self) -> None:
        self.failures = 0
        self.opened_until = 0.0

    def record_failure(self, now: float | None = None) -> None:
        self.failures += 1
        if self.failures >= self.fail_threshold:
            ts = time.time() if now is None else now
            self.opened_until = ts + self.cooldown_seconds

    @property
    def is_open(self) -> bool:
        return not self.allow()


_BREAKERS: dict[str, CircuitBreaker] = {name: CircuitBreaker() for name in ALL_SOURCES}


class SourceThrottle:
    """每个行情源的最小请求间隔 + 429/403 退避。"""

    def __init__(self, min_interval: float = DEFAULT_SOURCE_INTERVAL) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self._last: dict[str, float] = {}
        self._backoff: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, source: str, sleeper: Callable[[float], None] | None = None) -> float:
        pause = 0.0
        with self._lock:
            now = time.time()
            last = self._last.get(source, 0.0)
            extra = self._backoff.get(source, 0.0)
            pause = self.min_interval + extra - (now - last)
            if pause < 0:
                pause = 0.0
            self._last[source] = now + pause
        if pause > 0:
            (sleeper or time.sleep)(pause)
        return pause

    def punish(self, source: str, seconds: float = 20.0) -> None:
        with self._lock:
            prev = self._backoff.get(source, 0.0)
            self._backoff[source] = min(120.0, max(float(seconds), prev * 2 if prev else float(seconds)))

    def reward(self, source: str) -> None:
        with self._lock:
            self._backoff[source] = 0.0

    def reset(self) -> None:
        with self._lock:
            self._last.clear()
            self._backoff.clear()


_THROTTLE = SourceThrottle()


def get_source_throttle() -> SourceThrottle:
    return _THROTTLE


def reset_circuit_breakers() -> None:
    for name in ALL_SOURCES:
        _BREAKERS[name] = CircuitBreaker()
    _THROTTLE.reset()


def get_circuit_breaker(source: str) -> CircuitBreaker:
    if source not in _BREAKERS:
        _BREAKERS[source] = CircuitBreaker()
    return _BREAKERS[source]


def start_date(years: int) -> date:
    today = date.today()
    years = max(1, min(int(years or 10), 20))
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def _finite_price(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):  # NaN / Inf
        return None
    return num


def validate_ohlcv_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """
    Accept only complete real bars. Reject missing dates, non-positive close,
    or high < low. Never fills missing OHLC with invented values.
    """
    trade_date = str(row.get('trade_date') or '')[:10]
    if len(trade_date) != _ISO_DATE_LEN or trade_date[_MONTH_POS] != '-' or trade_date[_DAY_POS] != '-':
        return None
    close = _finite_price(row.get('close'))
    if close is None or close <= 0:
        return None
    open_ = _finite_price(row.get('open'))
    high = _finite_price(row.get('high'))
    low = _finite_price(row.get('low'))
    if open_ is None or high is None or low is None:
        return None
    if open_ <= 0 or high <= 0 or low <= 0:
        return None
    if high < low:
        return None
    volume = _finite_price(row.get('volume'))
    if volume is None or volume < 0:
        volume = 0.0
    turnover = _finite_price(row.get('turnover'))
    if turnover is None or turnover < 0:
        turnover = 0.0
    symbol = str(row.get('symbol') or '').strip()
    market = str(row.get('market') or 'US').strip().upper() or 'US'
    source = str(row.get('source') or '').strip()
    if not symbol or not source:
        return None
    return {
        'symbol': symbol,
        'market': market,
        'trade_date': trade_date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'turnover': turnover,
        'source': source,
    }


def validate_minute_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """分时/分钟点：trade_date 带时分，OHLC 允许四点同价。"""
    raw = str(row.get('trade_date') or '').strip().replace('T', ' ')
    if len(raw) < 16 or raw[4] != '-' or raw[7] != '-':
        return None
    close = _finite_price(row.get('close'))
    if close is None or close <= 0:
        return None
    price = close
    open_ = _finite_price(row.get('open')) or price
    high = _finite_price(row.get('high')) or price
    low = _finite_price(row.get('low')) or price
    if high < low:
        return None
    volume = _finite_price(row.get('volume'))
    if volume is None or volume < 0:
        volume = 0.0
    symbol = str(row.get('symbol') or '').strip()
    market = str(row.get('market') or 'US').strip().upper() or 'US'
    source = str(row.get('source') or '').strip() or 'tencent'
    if not symbol:
        return None
    stamp = raw[:19] if len(raw) >= 19 else raw[:16]
    if len(stamp) == 16:
        stamp = stamp + ':00'
    return {
        'symbol': symbol,
        'market': market,
        'trade_date': stamp,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'source': source,
    }


def merge_real_rows(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge by trade_date. Later sources in the call only fill missing dates."""
    by_date: dict[str, dict[str, Any]] = {}
    for rows in sources:
        for raw in rows or []:
            row = validate_ohlcv_row(raw)
            if row is None:
                continue
            by_date.setdefault(row['trade_date'], row)
    return [by_date[k] for k in sorted(by_date.keys())]


def _extract_json_array(text: str) -> list[Any]:
    start, end = text.find('['), text.rfind(']')
    if start == -1 or end <= start:
        return []
    try:
        arr = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return arr if isinstance(arr, list) else []


def _extract_json_object(text: str) -> dict[str, Any]:
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        return {}
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def sina_us_symbol(symbol: str) -> str:
    if symbol in INDEX_SOURCE_MAP:
        return INDEX_SOURCE_MAP[symbol]['sina']
    return symbol.replace('^', '')


def sina_cn_symbol(symbol: str) -> str:
    code = symbol.strip()
    if code.lower().startswith(('sh', 'sz')):
        return code.lower()
    if code.startswith(('6', '9')):
        return f'sh{code}'
    return f'sz{code}'


def sina_hk_symbol(symbol: str) -> str:
    code = symbol.upper().replace('.HK', '').replace('.HKG', '')
    return code.zfill(5) if code.isdigit() else code


def tencent_symbol(symbol: str, market: str) -> str:
    mkt = (market or 'US').upper()
    if symbol in INDEX_SOURCE_MAP:
        mapping = {'.DJI': 'usDJI', '.INX': 'usINX', '.IXIC': 'usIXIC'}
        return mapping.get(INDEX_SOURCE_MAP[symbol]['sina'], f'us{symbol.replace("^", "")}')
    if mkt == 'HK':
        code = symbol.upper().replace('.HK', '')
        return f'hk{code.zfill(5) if code.isdigit() else code}'
    if mkt == 'CN':
        return sina_cn_symbol(symbol)
    return f'us{symbol.replace("^", "")}'


def eastmoney_secid(symbol: str, market: str) -> str | None:
    mkt = (market or 'US').upper()
    if mkt == 'US':
        if symbol.startswith('^'):
            return None
        return f'105.{symbol}'
    if mkt == 'HK':
        code = symbol.upper().replace('.HK', '')
        return f'116.{code.zfill(5) if code.isdigit() else code}'
    if mkt == 'CN':
        code = symbol.lower().replace('sh', '').replace('sz', '')
        prefix = '1' if code.startswith(('6', '9')) else '0'
        return f'{prefix}.{code}'
    return None


def yahoo_symbol(symbol: str, market: str) -> str:
    mkt = (market or 'US').upper()
    if symbol in INDEX_SOURCE_MAP:
        return {'^DJI': '^DJI', '^GSPC': '^GSPC', '^IXIC': '^IXIC'}.get(symbol, symbol)
    if mkt == 'HK':
        if symbol.upper().endswith('.HK'):
            return symbol.upper()
        code = symbol.upper().replace('.HK', '')
        return f'{code.zfill(4) if code.isdigit() else code}.HK'
    if mkt == 'CN':
        code = symbol.lower().replace('sh', '').replace('sz', '')
        suffix = 'SS' if code.startswith(('6', '9')) else 'SZ'
        return f'{code}.{suffix}'
    return symbol.replace('^', '') if not symbol.startswith('^') else symbol


def stooq_symbol(symbol: str, market: str) -> str | None:
    mkt = (market or 'US').upper()
    if symbol.startswith('^'):
        return None
    if mkt == 'US':
        return f'{symbol.lower()}.us'
    if mkt == 'HK':
        code = symbol.upper().replace('.HK', '')
        return f'{code.lower()}.hk'
    return None


def netease_code(symbol: str, market: str) -> str | None:
    if (market or '').upper() != 'CN':
        return None
    code = symbol.lower().replace('sh', '').replace('sz', '')
    if not code.isdigit():
        return None
    prefix = '0' if code.startswith(('6', '9')) else '1'
    return f'{prefix}{code}'


def parse_sina_daily_items(
    items: list[Any], symbol: str, market: str, years: int, source: str = 'sina'
) -> list[dict[str, Any]]:
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        d = str(item.get('d') or item.get('day') or item.get('date') or '')[:10]
        if not d or d < start_str:
            continue
        parsed = validate_ohlcv_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': d,
                'open': item.get('o') if item.get('o') is not None else item.get('open'),
                'high': item.get('h') if item.get('h') is not None else item.get('high'),
                'low': item.get('l') if item.get('l') is not None else item.get('low'),
                'close': item.get('c') if item.get('c') is not None else item.get('close'),
                'volume': item.get('v') if item.get('v') is not None else item.get('volume'),
                'turnover': item.get('a') if item.get('a') is not None else item.get('amount'),
                'source': source,
            }
        )
        if parsed:
            rows.append(parsed)
    return rows


def parse_tencent_kline_payload(
    payload: dict[str, Any], symbol: str, market: str, years: int
) -> list[dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    for block in data.values():
        if not isinstance(block, dict):
            continue
        series = block.get('qfqday') or block.get('day') or block.get('hfqday') or []
        if not isinstance(series, list):
            continue
        for item in series:
            if not isinstance(item, (list, tuple)) or len(item) < _TX_SERIES_MIN_FIELDS:
                continue
            d = str(item[0])[:10]
            if not d or d < start_str:
                continue
            parsed = validate_ohlcv_row(
                {
                    'symbol': symbol,
                    'market': market,
                    'trade_date': d,
                    'open': item[1],
                    'close': item[2],
                    'high': item[3],
                    'low': item[4],
                    'volume': item[5] if len(item) > _TX_SERIES_MIN_FIELDS else 0,
                    'source': 'tencent',
                }
            )
            if parsed:
                rows.append(parsed)
    return rows


def parse_tencent_minute_payload(payload: dict[str, Any], symbol: str, market: str) -> list[dict[str, Any]]:  # noqa: PLR0912
    """腾讯分时：HHMM price volume [amount]，volume 多为累计，落库用增量。"""
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return []
    block = None
    for value in data.values():
        if isinstance(value, dict) and isinstance((value.get('data') or {}).get('data'), list):
            block = value.get('data') or {}
            break
    if not isinstance(block, dict):
        return []
    day = str(block.get('date') or '')
    if len(day) != 8 or not day.isdigit():
        return []
    day_iso = f'{day[:4]}-{day[4:6]}-{day[6:8]}'
    series = block.get('data') or []
    if not isinstance(series, list):
        return []
    out: list[dict[str, Any]] = []
    prev_vol = 0.0
    for item in series:
        text = str(item or '').strip()
        parts = text.split()
        if len(parts) < 2:
            continue
        hhmm = parts[0].zfill(4)
        if len(hhmm) != 4 or not hhmm.isdigit():
            continue
        price = _finite_price(parts[1])
        if price is None or price <= 0:
            continue
        cum = _finite_price(parts[2]) if len(parts) > 2 else 0.0
        if cum is None:
            cum = 0.0
        delta = cum - prev_vol
        if delta < 0:
            delta = cum
        prev_vol = cum
        stamp = f'{day_iso} {hhmm[:2]}:{hhmm[2:]}:00'
        parsed = validate_minute_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': stamp,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': delta,
                'source': 'tencent',
            }
        )
        if parsed:
            out.append(parsed)
    return out


def fetch_tencent_minute(symbol: str, market: str) -> list[dict[str, Any]]:
    mkt = (market or 'US').upper()
    code = tencent_symbol(symbol, mkt)
    url = TENCENT_MINUTE_URLS.get(mkt) or TENCENT_MINUTE_URLS['US']

    def _do() -> list[dict[str, Any]]:
        resp = _http_get(url, params={'code': code}, timeout=30)
        resp.raise_for_status()
        payload = resp.json() if resp.text else {}
        if not payload:
            payload = _extract_json_object(resp.text)
        return parse_tencent_minute_payload(payload if isinstance(payload, dict) else {}, symbol, mkt)

    return _call_source('tencent', _do)


def parse_eastmoney_klines(
    payload: dict[str, Any], symbol: str, market: str, years: int
) -> list[dict[str, Any]]:
    data = payload.get('data') if isinstance(payload, dict) else None
    klines = data.get('klines') if isinstance(data, dict) else None
    if not isinstance(klines, list):
        return []
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    for raw in klines:
        parts = str(raw).split(',')
        if len(parts) < _EM_MIN_PARTS:
            continue
        d = parts[0][:10]
        if not d or d < start_str:
            continue
        parsed = validate_ohlcv_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': d,
                'open': parts[1],
                'close': parts[2],
                'high': parts[3],
                'low': parts[4],
                'volume': parts[5],
                'turnover': parts[6] if len(parts) > _EM_MIN_PARTS else 0,
                'source': 'eastmoney',
            }
        )
        if parsed:
            rows.append(parsed)
    return rows


def parse_yahoo_chart(
    payload: dict[str, Any], symbol: str, market: str, years: int
) -> list[dict[str, Any]]:
    chart = payload.get('chart') if isinstance(payload, dict) else None
    results = chart.get('result') if isinstance(chart, dict) else None
    if not results:
        return []
    first = results[0] if isinstance(results, list) and results else None
    if not isinstance(first, dict):
        return []
    timestamps = first.get('timestamp') or []
    indicators = (first.get('indicators') or {}).get('quote') or []
    quote = indicators[0] if indicators else {}
    opens = quote.get('open') or []
    highs = quote.get('high') or []
    lows = quote.get('low') or []
    closes = quote.get('close') or []
    volumes = quote.get('volume') or []
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    for idx, ts in enumerate(timestamps):
        try:
            d = date.fromtimestamp(int(ts)).strftime('%Y-%m-%d')
        except (TypeError, ValueError, OSError):
            continue
        if d < start_str:
            continue
        parsed = validate_ohlcv_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': d,
                'open': opens[idx] if idx < len(opens) else None,
                'high': highs[idx] if idx < len(highs) else None,
                'low': lows[idx] if idx < len(lows) else None,
                'close': closes[idx] if idx < len(closes) else None,
                'volume': volumes[idx] if idx < len(volumes) else 0,
                'source': 'yahoo',
            }
        )
        if parsed:
            rows.append(parsed)
    return rows


def parse_stooq_csv(text: str, symbol: str, market: str, years: int) -> list[dict[str, Any]]:
    if not text or 'Date' not in text[:80]:
        return []
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for item in reader:
        d = str(item.get('Date') or '')[:10]
        if not d or d < start_str:
            continue
        parsed = validate_ohlcv_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': d,
                'open': item.get('Open'),
                'high': item.get('High'),
                'low': item.get('Low'),
                'close': item.get('Close'),
                'volume': item.get('Volume') or 0,
                'source': 'stooq',
            }
        )
        if parsed:
            rows.append(parsed)
    return rows


def parse_netease_csv(text: str, symbol: str, market: str, years: int) -> list[dict[str, Any]]:
    if not text or ('日期' not in text[:120] and 'DATE' not in text[:120].upper()):
        return []
    start_str = start_date(years).strftime('%Y-%m-%d')
    rows: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return []
    for cols in reader:
        if len(cols) < _NE_MIN_COLS:
            continue
        d = str(cols[0]).strip().replace('/', '-')[:10]
        if not d or d < start_str:
            continue
        # NetEase chddata: 日期,股票代码,名称,收盘价,最高价,最低价,开盘价,前收盘,涨跌额,涨跌幅,换手率,成交量,成交金额,...
        parsed = validate_ohlcv_row(
            {
                'symbol': symbol,
                'market': market,
                'trade_date': d,
                'close': cols[3] if len(cols) > _NE_CLOSE_COL else None,
                'high': cols[4] if len(cols) > _NE_HIGH_COL else None,
                'low': cols[5] if len(cols) > _NE_MIN_COLS else None,
                'open': cols[6] if len(cols) > _NE_OPEN_COL else None,
                'volume': cols[11] if len(cols) > _NE_VOL_COL else 0,
                'turnover': cols[12] if len(cols) > _NE_TURNOVER_COL else 0,
                'source': 'netease',
            }
        )
        if parsed:
            rows.append(parsed)
    return rows


def _http_get(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 20.0) -> httpx.Response:
    return httpx.get(
        url,
        params=params,
        headers=headers or DEFAULT_HEADERS,
        timeout=timeout,
        trust_env=False,
        follow_redirects=True,
    )


def _is_rate_limited(exc: Exception) -> bool:
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status in {429, 403, 418, 503}:
        return True
    text = str(exc).lower()
    return any(token in text for token in ('429', '403', 'too many', 'rate limit', 'banned'))


def _call_source(name: str, fn: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    breaker = get_circuit_breaker(name)
    if not breaker.allow():
        logger.info(f'[K线源] {name} 熔断中，跳过')
        return []
    _THROTTLE.wait(name)
    try:
        rows = fn() or []
        valid = [r for r in (validate_ohlcv_row(x) for x in rows) if r]
        if valid:
            breaker.record_success()
            _THROTTLE.reward(name)
            return valid
        # 无数据（停牌/窝轮）不是源挂了，不拉熔断
        return []
    except Exception as exc:
        breaker.record_failure()
        if _is_rate_limited(exc):
            _THROTTLE.punish(name, 30.0)
            logger.warning(f'[K线源] {name} 疑似限流，拉长间隔: {exc}')
        else:
            logger.warning(f'[K线源] {name} 拉取失败: {exc}')
        return []


def fetch_sina(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    mkt = (market or 'US').upper()

    def _do() -> list[dict[str, Any]]:
        if mkt == 'US':
            resp = _http_get(
                SINA_US_DAILY_URL,
                params={'symbol': sina_us_symbol(symbol), '___qn': '3n'},
                headers=SINA_HEADERS,
                timeout=45,
            )
            resp.raise_for_status()
            return parse_sina_daily_items(_extract_json_array(resp.text), symbol, mkt, years)
        if mkt == 'HK':
            resp = _http_get(
                SINA_HK_DAILY_URL,
                params={'symbol': sina_hk_symbol(symbol)},
                headers=SINA_HEADERS,
                timeout=45,
            )
            resp.raise_for_status()
            return parse_sina_daily_items(_extract_json_array(resp.text), symbol, mkt, years)
        resp = _http_get(
            SINA_CN_KLINE_URL,
            params={'symbol': sina_cn_symbol(symbol), 'scale': 240, 'ma': 'no', 'datalen': 2048},
            headers=SINA_HEADERS,
            timeout=45,
        )
        resp.raise_for_status()
        try:
            items = resp.json()
        except Exception:
            items = _extract_json_array(resp.text)
        return parse_sina_daily_items(items if isinstance(items, list) else [], symbol, mkt, years)

    return _call_source('sina', _do)


def fetch_tencent(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    mkt = (market or 'US').upper()

    def _do() -> list[dict[str, Any]]:
        tencent_code = tencent_symbol(symbol, mkt)
        url = TENCENT_HK_FQKLINE_URL if mkt == 'HK' else TENCENT_FQKLINE_URL
        param = f'{tencent_code},day,,,2000,qfq'
        resp = _http_get(url, params={'param': param}, timeout=45)
        resp.raise_for_status()
        payload = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else _extract_json_object(resp.text)
        if not payload:
            payload = _extract_json_object(resp.text)
        return parse_tencent_kline_payload(payload, symbol, mkt, years)

    return _call_source('tencent', _do)


def fetch_eastmoney(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    secid = eastmoney_secid(symbol, market)
    if not secid:
        return []

    def _do() -> list[dict[str, Any]]:
        resp = _http_get(
            EASTMONEY_KLINE_URL,
            params={
                'secid': secid,
                'klt': 101,
                'fqt': 1,
                'lmt': 2400,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            },
            timeout=45,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.text else {}
        return parse_eastmoney_klines(payload if isinstance(payload, dict) else {}, symbol, market, years)

    return _call_source('eastmoney', _do)


def fetch_yahoo(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    ysym = yahoo_symbol(symbol, market)

    def _do() -> list[dict[str, Any]]:
        url = YAHOO_CHART_URL.format(symbol=quote(ysym, safe='^.'))
        resp = _http_get(
            url,
            params={'interval': '1d', 'range': f'{max(1, min(years, 10))}y', 'events': 'div,splits'},
            timeout=45,
        )
        resp.raise_for_status()
        payload = resp.json() if resp.text else {}
        return parse_yahoo_chart(payload if isinstance(payload, dict) else {}, symbol, market, years)

    return _call_source('yahoo', _do)


def fetch_stooq(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    ssym = stooq_symbol(symbol, market)
    if not ssym:
        return []

    def _do() -> list[dict[str, Any]]:
        resp = _http_get(STOOQ_CSV_URL, params={'s': ssym, 'i': 'd'}, timeout=45)
        resp.raise_for_status()
        return parse_stooq_csv(resp.text, symbol, market, years)

    return _call_source('stooq', _do)


def fetch_netease(symbol: str, market: str, years: int = 10) -> list[dict[str, Any]]:
    code = netease_code(symbol, market)
    if not code:
        return []

    def _do() -> list[dict[str, Any]]:
        start = start_date(years).strftime('%Y%m%d')
        end = date.today().strftime('%Y%m%d')
        resp = _http_get(
            NETEASE_CHD_URL,
            params={'code': code, 'start': start, 'end': end, 'fields': 'TCLOSE;HIGH;LOW;TOPEN;VOTURNOVER;VATURNOVER'},
            timeout=45,
        )
        resp.raise_for_status()
        return parse_netease_csv(resp.text, symbol, market, years)

    return _call_source('netease', _do)


_FETCHERS: dict[str, Callable[[str, str, int], list[dict[str, Any]]]] = {
    'sina': fetch_sina,
    'tencent': fetch_tencent,
    'eastmoney': fetch_eastmoney,
    'yahoo': fetch_yahoo,
    'stooq': fetch_stooq,
    'netease': fetch_netease,
}


def fetch_real_klines(
    symbol: str,
    market: str = 'US',
    years: int = 10,
    use_fallbacks: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Fetch real daily bars. Primary Sina then Tencent, then fallbacks.
    首源已有足够 K 线时不再打后续源。Empty when every source fails — never fake.
    全市场慢同步应关掉 fallbacks，避免 Yahoo 429 把进程睡死。
    """
    symbol = (symbol or '').strip()
    market = (market or 'US').strip().upper()
    if not symbol:
        return [], []

    used: list[str] = []
    merged: list[dict[str, Any]] = []
    primaries = primary_sources_for(market)

    for name in primaries:
        rows = _FETCHERS[name](symbol, market, years)
        if rows:
            used.append(name)
            merged = merge_real_rows(merged, rows)
            if len(merged) >= MIN_BARS_STOP:
                return merged, used

    if not merged and use_fallbacks:
        primaries_blocked = all(not get_circuit_breaker(name).allow() for name in primaries)
        if primaries_blocked:
            logger.warning(f'[K线源] {symbol} 主源均熔断，跳过回退以免继续打穿')
            return [], []
        for name in FALLBACK_SOURCES:
            rows = _FETCHERS[name](symbol, market, years)
            if rows:
                used.append(name)
                merged = merge_real_rows(merged, rows)
                break

    return merged, used
