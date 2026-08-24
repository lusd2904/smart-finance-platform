"""
全市场股票代码抓取与落库。

美股：新浪 US_CategoryService（失败时回退 NASDAQ Trader 官方列表）
A股：新浪沪深A（hs_a，含科创/创业/北交所）
港股：新浪港股 qbgg_hk

写入 market_instrument.category='listed'。已有精选分类（mag7/star/index/...）只更新名称，不覆盖分类。
K 线日同步仍只走 TARGET_INSTRUMENTS，本模块不拉全市场行情。
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from module_market.constant.instruments import LISTED_CATEGORY
from utils.http_fetch import fetch
from utils.log_util import logger

if TYPE_CHECKING:
    from collections.abc import Callable

UA = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    ),
}

SINA_HEADERS = {
    **UA,
    'Referer': 'https://finance.sina.com.cn',
}

EM_HEADERS = {
    **UA,
    'Referer': 'https://quote.eastmoney.com/',
}

SINA_CN_URL = (
    'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'Market_Center.getHQNodeData'
)
SINA_HK_URL = (
    'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'Market_Center.getHKStockData'
)
SINA_US_URL = (
    'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20t=/'
    'US_CategoryService.getList'
)
NASDAQ_LISTED_URL = 'https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt'
NASDAQ_OTHER_URL = 'https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt'
EM_HOSTS = (
    '80.push2.eastmoney.com',
    '82.push2.eastmoney.com',
    'push2delay.eastmoney.com',
    'push2.eastmoney.com',
)
EM_CN_FS = ('m:1+t:2', 'm:1+t:23', 'm:0+t:6', 'm:0+t:80', 'm:0+t:81')
EM_HK_FS = ('m:128+t:3', 'm:128+t:4', 'm:128+t:1', 'm:128+t:2')
EM_US_FS = ('m:105', 'm:106', 'm:107')

PAGE_SLEEP = 0.12
MAX_PAGES = 400
CN_PAGE_SIZE = 80
HK_PAGE_SIZE = 80
US_PAGE_SIZE = 100
EM_PAGE_SIZE = 100
UPSERT_CHUNK = 400
US_SYMBOL_RE = re.compile(r'^[A-Z][A-Z0-9.\-]{0,15}$')
CN_SYMBOL_LEN = 6
HK_CODE_MIN_LEN_FOR_ETF = 5
HK_SYMBOL_MAX_LEN = 4
NASDAQ_MIN_PARTS = 4
NASDAQ_TEST_FLAG_IDX = 4
NASDAQ_ETF_FLAG_IDX = 6
NASDAQ_OTHER_MIN_PARTS = 7
MIN_SINA_LISTING_ROWS = 500


def _http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    return fetch(url, timeout_s=timeout, headers={**UA, **(headers or {})})


def _clip_name(name: str | None) -> str:
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    return text[:100]


def _prefer_cname(cname: str | None, name: str | None) -> str:
    cn = _clip_name(cname)
    en = _clip_name(name)
    if cn and any('\u4e00' <= ch <= '\u9fff' for ch in cn):
        return cn
    return cn or en


def listed_category_after_upsert(existing_category: str | None, incoming: str = LISTED_CATEGORY) -> str:
    """精选池分类保留；仅 listed/空分类被全市场同步覆盖。"""
    current = (existing_category or '').strip()
    if not current or current == LISTED_CATEGORY:
        return incoming or LISTED_CATEGORY
    return current


def normalize_cn_symbol(raw: str | None) -> str | None:
    text = str(raw or '').strip().upper()
    if not text:
        return None
    text = re.sub(r'^(SH|SZ|BJ|SS)', '', text)
    text = text.replace('.SS', '').replace('.SZ', '').replace('.BJ', '')
    if text.isdigit() and len(text) == CN_SYMBOL_LEN:
        return text
    return None


def _is_hk_non_equity(symbol: str, name: str) -> bool:
    upper = (name or '').upper()
    if re.search(r'-(W?R|SWR|RMB)$', name or '', flags=re.IGNORECASE):
        return True
    if 'ETF' in upper or 'ETN' in upper:
        return True
    code = symbol.replace('.HK', '')
    return len(code) >= HK_CODE_MIN_LEN_FOR_ETF


def _is_us_non_equity(name: str) -> bool:
    upper = (name or '').upper()
    return 'ETF' in upper or 'ETN' in upper or ' FUND' in upper or upper.endswith('FUND')


def normalize_hk_symbol(raw: str | None) -> str | None:
    text = str(raw or '').strip().upper().replace('.HK', '')
    text = re.sub(r'[^0-9]', '', text)
    if not text:
        return None
    text = text.lstrip('0') or '0'
    if len(text) > HK_SYMBOL_MAX_LEN:
        return None
    padded = text.zfill(HK_SYMBOL_MAX_LEN) if len(text) <= HK_SYMBOL_MAX_LEN else text
    return f'{padded}.HK'


def normalize_us_symbol(raw: str | None) -> str | None:
    text = str(raw or '').strip().upper()
    if ' ' in text:
        return None
    if text.endswith('.US'):
        text = text[:-3]
    if not text or text.startswith('^') or not US_SYMBOL_RE.match(text):
        return None
    if text.endswith(('.W', '.U', '.R')):
        return None
    return text


def parse_eastmoney_diff(rows: Any, market: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get('f12') or '').strip()
        name = _clip_name(row.get('f14') or code)
        if market == 'CN':
            symbol = normalize_cn_symbol(code)
        elif market == 'HK':
            symbol = normalize_hk_symbol(code)
        else:
            symbol = normalize_us_symbol(code)
        if not symbol:
            continue
        if market == 'HK' and _is_hk_non_equity(symbol, name):
            continue
        if market == 'US' and _is_us_non_equity(name):
            continue
        out.append({'symbol': symbol, 'name': name or symbol, 'market': market, 'category': LISTED_CATEGORY})
    return out


def parse_sina_cn_rows(rows: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_cn_symbol(row.get('code') or row.get('symbol'))
        if not symbol:
            continue
        name = _clip_name(row.get('name') or symbol)
        out.append({'symbol': symbol, 'name': name, 'market': 'CN', 'category': LISTED_CATEGORY})
    return out


def parse_sina_hk_rows(rows: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_hk_symbol(row.get('symbol') or row.get('code'))
        if not symbol:
            continue
        name = _prefer_cname(row.get('name'), row.get('engname') or symbol)
        if _is_hk_non_equity(symbol, name):
            continue
        out.append({'symbol': symbol, 'name': name, 'market': 'HK', 'category': LISTED_CATEGORY})
    return out


def parse_sina_us_jsonp(text: str) -> tuple[int, list[dict[str, str]]]:
    start = text.find('(')
    end = text.rfind(')')
    if start < 0 or end <= start:
        return 0, []
    try:
        payload = json.loads(text[start + 1 : end])
    except json.JSONDecodeError:
        return 0, []
    if not isinstance(payload, dict):
        return 0, []
    try:
        total = int(payload.get('count') or 0)
    except (TypeError, ValueError):
        total = 0
    out: list[dict[str, str]] = []
    for row in payload.get('data') or []:
        if not isinstance(row, dict):
            continue
        symbol = normalize_us_symbol(row.get('symbol'))
        if not symbol:
            continue
        name = _prefer_cname(row.get('cname'), row.get('name') or symbol)
        if _is_us_non_equity(name) or _is_us_non_equity(row.get('name') or ''):
            continue
        out.append({'symbol': symbol, 'name': name, 'market': 'US', 'category': LISTED_CATEGORY})
    return total, out


def parse_nasdaq_listed(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in (text or '').splitlines():
        if not line or line.startswith(('File Creation', 'Symbol|')):
            continue
        parts = line.split('|')
        if len(parts) < NASDAQ_MIN_PARTS:
            continue
        symbol = normalize_us_symbol(parts[0])
        name = _clip_name(parts[1] if len(parts) > 1 else symbol)
        test_flag = parts[3]
        etf_flag = parts[NASDAQ_ETF_FLAG_IDX] if len(parts) > NASDAQ_ETF_FLAG_IDX else 'N'
        if not symbol or str(test_flag).upper() == 'Y' or str(etf_flag).upper() == 'Y':
            continue
        if _is_us_non_equity(name):
            continue
        out.append({'symbol': symbol, 'name': name or symbol, 'market': 'US', 'category': LISTED_CATEGORY})
    return out


def parse_nasdaq_otherlisted(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in (text or '').splitlines():
        if not line or line.startswith(('File Creation', 'ACT Symbol|')):
            continue
        parts = line.split('|')
        if len(parts) < NASDAQ_OTHER_MIN_PARTS:
            continue
        if str(parts[6]).upper() == 'Y':
            continue
        if len(parts) > NASDAQ_TEST_FLAG_IDX and str(parts[NASDAQ_TEST_FLAG_IDX]).upper() == 'Y':
            continue
        symbol = normalize_us_symbol(parts[0])
        if not symbol:
            continue
        name = _clip_name(parts[1] if len(parts) > 1 else symbol)
        if _is_us_non_equity(name):
            continue
        out.append({'symbol': symbol, 'name': name or symbol, 'market': 'US', 'category': LISTED_CATEGORY})
    return out


def dedupe_instruments(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        symbol = row.get('symbol') or ''
        if not symbol or symbol in seen:
            continue
        seen[symbol] = row
    return list(seen.values())


def _paginate(
    fetch_page: Callable[[int], tuple[list[dict[str, str]], int] | list[dict[str, str]]],
    page_size: int,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, str]]:
    """按上游原始条数翻页；过滤涡轮/ETF 后剩余变少不能当成最后一页。"""
    out: list[dict[str, str]] = []
    for page in range(1, max_pages + 1):
        result = fetch_page(page)
        if isinstance(result, tuple):
            rows, raw_n = result
        else:
            rows, raw_n = result, len(result)
        if raw_n <= 0:
            break
        out.extend(rows)
        time.sleep(PAGE_SLEEP)
    return out


def fetch_sina_cn() -> list[dict[str, str]]:
    def page(pn: int) -> tuple[list[dict[str, str]], int]:
        qs = urlencode({'page': pn, 'num': CN_PAGE_SIZE, 'sort': 'symbol', 'asc': 1, 'node': 'hs_a', '_s_r_a': 'page'})
        raw = _http_get(f'{SINA_CN_URL}?{qs}', SINA_HEADERS)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return [], 0
        rows = payload if isinstance(payload, list) else []
        return parse_sina_cn_rows(rows), len(rows)

    return dedupe_instruments(_paginate(page, CN_PAGE_SIZE))


def fetch_sina_hk() -> list[dict[str, str]]:
    def page(pn: int) -> tuple[list[dict[str, str]], int]:
        qs = urlencode({'page': pn, 'num': HK_PAGE_SIZE, 'sort': 'symbol', 'asc': 1, 'node': 'qbgg_hk'})
        raw = _http_get(f'{SINA_HK_URL}?{qs}', SINA_HEADERS)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return [], 0
        rows = payload if isinstance(payload, list) else []
        return parse_sina_hk_rows(rows), len(rows)

    return dedupe_instruments(_paginate(page, HK_PAGE_SIZE))


def fetch_sina_us() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    total = 0
    for page in range(1, MAX_PAGES + 1):
        qs = urlencode({'page': page, 'num': US_PAGE_SIZE, 'sort': '', 'asc': 1, 'market': '', 'id': ''})
        raw = _http_get(f'{SINA_US_URL}?{qs}', SINA_HEADERS)
        count, rows = parse_sina_us_jsonp(raw)
        if count:
            total = count
        start = raw.find('(')
        end = raw.rfind(')')
        raw_n = 0
        if start >= 0 and end > start:
            try:
                payload = json.loads(raw[start + 1 : end])
                raw_n = len(payload.get('data') or []) if isinstance(payload, dict) else 0
            except json.JSONDecodeError:
                raw_n = len(rows)
        if raw_n <= 0:
            break
        out.extend(rows)
        if total and page * US_PAGE_SIZE >= total:
            break
        if raw_n < US_PAGE_SIZE:
            break
        time.sleep(PAGE_SLEEP)
    return dedupe_instruments(out)


def fetch_nasdaq_us() -> list[dict[str, str]]:
    listed = parse_nasdaq_listed(_http_get(NASDAQ_LISTED_URL, UA))
    other = parse_nasdaq_otherlisted(_http_get(NASDAQ_OTHER_URL, UA))
    return dedupe_instruments(listed + other)


def _fetch_eastmoney_fs(fs: str, market: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    last_err: Exception | None = None
    for host in EM_HOSTS:
        try:
            for page in range(1, MAX_PAGES + 1):
                qs = urlencode(
                    {
                        'pn': page,
                        'pz': EM_PAGE_SIZE,
                        'po': 1,
                        'np': 1,
                        'fltt': 2,
                        'invt': 2,
                        'fid': 'f12',
                        'fs': fs,
                        'fields': 'f12,f13,f14',
                    }
                )
                raw = _http_get(f'https://{host}/api/qt/clist/get?{qs}', EM_HEADERS)
                payload = json.loads(raw)
                data = payload.get('data') or {}
                diff = data.get('diff') or []
                raw_n = len(diff) if isinstance(diff, dict) else len(diff or [])
                rows = parse_eastmoney_diff(diff, market)
                if raw_n <= 0:
                    break
                out.extend(rows)
                total = int(data.get('total') or 0)
                fetched_raw = page * EM_PAGE_SIZE
                if total and fetched_raw >= total:
                    break
                if raw_n < EM_PAGE_SIZE:
                    break
                time.sleep(PAGE_SLEEP)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            out = []
            continue
    if last_err and not out:
        logger.warning(f'[listings] eastmoney {market} {fs} failed: {last_err}')
    return out


def fetch_eastmoney_market(market: str) -> list[dict[str, str]]:
    fs_list = {'CN': EM_CN_FS, 'HK': EM_HK_FS, 'US': EM_US_FS}[market]
    rows: list[dict[str, str]] = []
    for fs in fs_list:
        rows.extend(_fetch_eastmoney_fs(fs, market))
        time.sleep(PAGE_SLEEP)
    return dedupe_instruments(rows)


def fetch_market(market: str) -> list[dict[str, str]]:
    code = (market or '').strip().upper()
    primary: list[dict[str, str]] = []
    try:
        if code == 'CN':
            primary = fetch_sina_cn()
        elif code == 'HK':
            primary = fetch_sina_hk()
        elif code == 'US':
            primary = fetch_sina_us()
        else:
            raise ValueError(f'不支持的市场: {market}')
    except Exception as exc:
        logger.warning(f'[listings] sina {code} failed: {exc}')
        primary = []
    if len(primary) >= MIN_SINA_LISTING_ROWS:
        return primary
    logger.info(f'[listings] {code} sina got {len(primary)}, trying fallback')
    if code == 'US':
        try:
            nasdaq = fetch_nasdaq_us()
            if len(nasdaq) > len(primary):
                primary = nasdaq
        except Exception as exc:
            logger.warning(f'[listings] nasdaq fallback failed: {exc}')
    try:
        em_rows = fetch_eastmoney_market(code)
        if len(em_rows) > len(primary):
            primary = em_rows
    except Exception as exc:
        logger.warning(f'[listings] eastmoney {code} fallback failed: {exc}')
    return primary


def fetch_all(markets: list[str] | None = None) -> dict[str, list[dict[str, str]]]:
    wanted = [m.upper() for m in (markets or ['US', 'CN', 'HK'])]
    result: dict[str, list[dict[str, str]]] = {}
    for market in wanted:
        rows = fetch_market(market)
        result[market] = rows
        logger.info(f'[listings] fetched {market}={len(rows)}')
    return result


def _connect(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> Any:
    import pymysql

    if host:
        return pymysql.connect(
            host=host,
            port=int(port or 3306),
            user=user or 'root',
            password=password or '',
            database=database or 'sentiment-ai',
            charset='utf8mb4',
            autocommit=True,
        )
    from module_market.service.sync_service import MarketSyncService

    conn = MarketSyncService._app_db_conn()
    if conn is None:
        raise RuntimeError('无法连接业务 MySQL')
    return conn


def upsert_listed_rows(conn: Any, rows: list[dict[str, str]]) -> dict[str, int]:
    unique = dedupe_instruments(rows)
    if not unique:
        return {'fetched': 0, 'affected': 0}
    sql = """
    INSERT INTO market_instrument (symbol, name, market, category, enabled, create_time)
    VALUES (%s, %s, %s, %s, '1', NOW())
    ON DUPLICATE KEY UPDATE
      name = IF(
        category = 'listed' OR category IS NULL OR category = '',
        IF(VALUES(name) IS NULL OR VALUES(name) = '', name, VALUES(name)),
        name
      ),
      market = IF(category = 'listed' OR category IS NULL OR category = '', VALUES(market), market),
      category = IF(category = 'listed' OR category IS NULL OR category = '', VALUES(category), category)
    """
    affected = 0
    with conn.cursor() as cur:
        for i in range(0, len(unique), UPSERT_CHUNK):
            chunk = unique[i : i + UPSERT_CHUNK]
            payload = [(r['symbol'], r.get('name') or r['symbol'], r['market'], LISTED_CATEGORY) for r in chunk]
            cur.executemany(sql, payload)
            affected += int(cur.rowcount or 0)
    if hasattr(conn, 'commit'):
        try:
            conn.commit()
        except Exception:
            pass
    return {'fetched': len(unique), 'affected': affected}


def count_by_market(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            'SELECT market, category, COUNT(*) AS c FROM market_instrument GROUP BY market, category ORDER BY market, category'
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append({'market': row.get('market'), 'category': row.get('category'), 'count': row.get('c')})
        else:
            out.append({'market': row[0], 'category': row[1], 'count': row[2]})
    return out


class ListingService:
    """全市场代码同步（同步 IO，可放线程池）。"""

    @classmethod
    def sync(
        cls,
        markets: list[str] | None = None,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        conn: Any | None = None,
    ) -> dict[str, Any]:
        fetched = fetch_all(markets)
        close_conn = False
        if conn is None:
            conn = _connect(host=host, port=port, user=user, password=password, database=database)
            close_conn = True
        try:
            all_rows: list[dict[str, str]] = []
            for rows in fetched.values():
                all_rows.extend(rows)
            upsert = upsert_listed_rows(conn, all_rows)
            breakdown = count_by_market(conn)
            total = sum(int(item['count']) for item in breakdown)
            result = {
                'fetched': {m: len(rows) for m, rows in fetched.items()},
                'upserted': upsert['fetched'],
                'affected': upsert['affected'],
                'total': total,
                'byMarket': breakdown,
            }
            logger.info(f'[listings] sync done {result}')
            return result
        finally:
            if close_conn:
                try:
                    conn.close()
                except Exception:
                    pass
