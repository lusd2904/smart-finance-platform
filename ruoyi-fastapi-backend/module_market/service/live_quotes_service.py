"""个股最新价：盘中长桥实时 + 腾讯 qt.gtimg.cn 补缺 + Redis 短缓存。

对照 Open-Terminal / vietnam-stock-market-api：HTTP 快照 + WS 订阅增量。
不走 Influx，避免自选页轮询打时序库。收市市场只走腾讯。
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from module_market.service.index_session import is_live_kline_session
from module_market.service.kline_sources import tencent_symbol
from module_market.service.tencent_quote import fetch_tencent_batch
from module_quant.service.longbridge.auth import QUOTE_SYMBOL_LIMIT
from module_quant.service.longbridge_service import LongbridgeService
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.time_format_util import now_beijing

MAX_LIVE_SYMBOLS = 80
FETCH_CHUNK = 40
CACHE_TTL_SECONDS = 5
CACHE_PREFIX = 'market:live:quotes:'
_MARKETS = frozenset({'US', 'HK', 'CN'})
_LB_SUFFIXES = ('.US', '.HK', '.SH', '.SZ')


def normalize_symbol_market(symbol: str, market: str | None = None) -> tuple[str, str] | None:
    raw = str(symbol or '').strip().upper()
    if not raw:
        return None
    mkt = str(market or 'US').strip().upper()
    if raw.endswith('.US'):
        raw, mkt = raw[:-3], 'US'
    elif raw.endswith('.HK'):
        raw, mkt = raw[:-3], 'HK'
    elif raw.endswith(('.SS', '.SZ', '.SH')):
        raw, mkt = raw.split('.', maxsplit=1)[0], 'CN'
    if mkt not in _MARKETS:
        mkt = 'US'
    if not raw:
        return None
    return raw, mkt


def parse_subscribe_symbols(raw: Any) -> list[tuple[str, str]]:
    """接受 ['AAPL:US', '00700.HK'] 或 [{symbol, market}]，去重并封顶。"""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    items = raw if isinstance(raw, list) else []
    for item in items:
        symbol = ''
        market = 'US'
        if isinstance(item, str):
            text = item.strip()
            if ':' in text:
                symbol, market = text.split(':', maxsplit=1)
            elif '.' in text:
                symbol, market = text.rsplit('.', maxsplit=1)
            else:
                symbol = text
        elif isinstance(item, dict):
            symbol = str(item.get('symbol') or '')
            market = str(item.get('market') or 'US')
        else:
            continue
        normalized = normalize_symbol_market(symbol, market)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        pairs.append(normalized)
        if len(pairs) >= MAX_LIVE_SYMBOLS:
            break
    return pairs


def parse_symbols_query(raw: str | None) -> list[tuple[str, str]]:
    if not raw:
        return []
    return parse_subscribe_symbols([part.strip() for part in str(raw).split(',') if part.strip()])


def _strip_longbridge_suffix(symbol: str) -> str:
    raw = str(symbol or '').strip().upper()
    for suffix in _LB_SUFFIXES:
        if raw.endswith(suffix):
            return raw[: -len(suffix)]
    return raw


def _hk_code_aliases(symbol: str) -> list[str]:
    raw = str(symbol or '').strip().upper()
    if not raw.isdigit():
        return [raw] if raw else []
    aliases = [raw, raw.lstrip('0') or '0', raw.zfill(5)]
    out: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _lookup_live_pair(quote_symbol: str, by_lb: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    raw = str(quote_symbol or '').strip().upper()
    if not raw:
        return None
    pair = by_lb.get(raw)
    if pair is not None:
        return pair
    stripped = _strip_longbridge_suffix(raw)
    pair = by_lb.get(stripped)
    if pair is not None:
        return pair
    for alias in _hk_code_aliases(stripped):
        pair = by_lb.get(alias)
        if pair is not None:
            return pair
    return None


def _overlay_hub_quotes(
    items: list[dict[str, Any]], pairs: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    from module_market.service.quote_subscribe_hub import QuoteSubscribeHub

    hub_items = QuoteSubscribeHub.latest_for(pairs)
    if not hub_items:
        return items
    by_key: dict[tuple[str, str], dict[str, Any]] = {
        (str(item.get('symbol') or ''), str(item.get('market') or 'US')): item for item in items
    }
    for item in hub_items:
        by_key[(item['symbol'], item['market'])] = item
    return [by_key[pair] for pair in pairs if pair in by_key]


def _payload_source(items: list[dict[str, Any]]) -> str:
    sources = {str(item.get('source') or '') for item in items}
    has_lb = 'longbridge' in sources
    has_tx = 'tencent' in sources
    if has_lb and has_tx:
        return 'longbridge+tencent'
    if has_lb:
        return 'longbridge'
    return 'tencent'


def _quote_item(
    symbol: str,
    market: str,
    *,
    last: Any,
    prev: Any,
    change_pct: Any,
    quote_time: Any,
    name: Any,
    source: str,
) -> dict[str, Any]:
    if change_pct is None and last and prev:
        change_pct = round((float(last) / float(prev) - 1.0) * 100, 2)
    return {
        'symbol': symbol,
        'market': market,
        'name': name or symbol,
        'last': last,
        'prevClose': prev,
        'changePct': change_pct,
        'changeRate': change_pct,
        'quoteTime': quote_time,
        'source': source,
    }


def _partition_live_pairs(
    pairs: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    live: list[tuple[str, str]] = []
    rest: list[tuple[str, str]] = []
    for pair in pairs:
        try:
            in_live = bool(is_live_kline_session(pair[1]))
        except Exception:
            in_live = False
        if in_live:
            live.append(pair)
        else:
            rest.append(pair)
    return live, rest


def _longbridge_symbol_map(pairs: list[tuple[str, str]]) -> tuple[list[str], dict[str, tuple[str, str]]]:
    lb_symbols: list[str] = []
    by_lb: dict[str, tuple[str, str]] = {}
    for symbol, market in pairs:
        try:
            lb_sym = str(LongbridgeService.to_longbridge_symbol(symbol, market) or '').strip().upper()
        except Exception:
            continue
        if not lb_sym:
            continue
        if lb_sym not in by_lb:
            lb_symbols.append(lb_sym)
        pair = (symbol, market)
        by_lb[lb_sym] = pair
        by_lb[str(symbol).upper()] = pair
        stripped = _strip_longbridge_suffix(lb_sym)
        if stripped:
            by_lb.setdefault(stripped, pair)
            for alias in _hk_code_aliases(stripped):
                by_lb.setdefault(alias, pair)
            for alias in _hk_code_aliases(str(symbol).upper()):
                by_lb.setdefault(alias, pair)
    return lb_symbols, by_lb


def _longbridge_quote_last(quote: dict[str, Any]) -> Any:
    last = quote.get('lastDone')
    return last if last is not None else quote.get('last')


def _items_from_longbridge_quotes(
    quotes: list[Any],
    by_lb: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for quote in quotes:
        if not isinstance(quote, dict):
            continue
        last = _longbridge_quote_last(quote)
        if last is None:
            continue
        pair = _lookup_live_pair(str(quote.get('symbol') or ''), by_lb)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        change_pct = quote.get('changeRate')
        if change_pct is None:
            change_pct = quote.get('changePct')
        items.append(
            _quote_item(
                pair[0],
                pair[1],
                last=last,
                prev=quote.get('prevClose'),
                change_pct=change_pct,
                quote_time=quote.get('quoteTime') or quote.get('timestamp'),
                name=quote.get('name') or pair[0],
                source='longbridge',
            )
        )
    return items


def _request_longbridge_quotes(lb_symbols: list[str]) -> list[Any]:
    quotes: list[Any] = []
    try:
        limit = max(1, int(QUOTE_SYMBOL_LIMIT))
        for i in range(0, len(lb_symbols), limit):
            result = LongbridgeService.get_realtime_quote(lb_symbols[i : i + limit]) or {}
            quotes.extend(result.get('quotes') or [])
    except Exception as exc:
        logger.warning(f'[live-quotes] 长桥批量失败 n={len(lb_symbols)}: {exc}')
        return []
    return quotes


def _fetch_longbridge_items(pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    if not pairs:
        return []
    try:
        configured = LongbridgeService.is_configured()
    except Exception as exc:
        logger.warning(f'[live-quotes] 长桥配置检测失败: {exc}')
        return []
    if not configured:
        return []
    lb_symbols, by_lb = _longbridge_symbol_map(pairs)
    if not lb_symbols:
        return []
    return _items_from_longbridge_quotes(_request_longbridge_quotes(lb_symbols), by_lb)


def _fetch_tencent_items(pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
    code_map: dict[str, tuple[str, str]] = {}
    codes: list[str] = []
    for symbol, market in pairs:
        try:
            code = tencent_symbol(symbol, market)
        except Exception:
            continue
        if not code or code in code_map:
            continue
        code_map[code] = (symbol, market)
        codes.append(code)
    quotes: dict[str, dict[str, Any]] = {}
    for i in range(0, len(codes), FETCH_CHUNK):
        chunk = codes[i : i + FETCH_CHUNK]
        try:
            quotes.update(fetch_tencent_batch(chunk))
        except Exception as exc:
            logger.warning(f'[live-quotes] 腾讯批量失败 n={len(chunk)}: {exc}')
    items: list[dict[str, Any]] = []
    for code, (symbol, market) in code_map.items():
        quote = quotes.get(code)
        if not quote or quote.get('last') is None:
            continue
        last = quote['last']
        prev = quote.get('prevClose')
        items.append(
            _quote_item(
                symbol,
                market,
                last=last,
                prev=prev,
                change_pct=quote.get('changePct'),
                quote_time=quote.get('quoteTime'),
                name=quote.get('name') or symbol,
                source='tencent',
            )
        )
    return items


class LiveQuotesService:
    """自选/交易台订阅的个股最新价。"""

    @classmethod
    async def get_quotes(cls, pairs: list[tuple[str, str]]) -> dict[str, Any]:
        normalized = parse_subscribe_symbols([{'symbol': s, 'market': m} for s, m in pairs])
        if not normalized:
            return {
                'items': [],
                'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
                'source': 'empty',
                'cached': False,
            }
        from module_market.service.quote_subscribe_hub import QuoteSubscribeHub

        hub_items = QuoteSubscribeHub.latest_for(normalized)
        hub_by_key: dict[tuple[str, str], dict[str, Any]] = {
            (item['symbol'], item['market']): item for item in hub_items
        }
        if all(pair in hub_by_key for pair in normalized):
            items = [hub_by_key[pair] for pair in normalized]
            return {
                'items': items,
                'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
                'source': _payload_source(items),
                'cached': False,
            }
        cache_key = CACHE_PREFIX + hashlib.sha1(
            ','.join(f'{m}:{s}' for s, m in normalized).encode('utf-8')
        ).hexdigest()[:16]
        cached = await cache_get_json(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get('items'), list):
            items = _overlay_hub_quotes(list(cached.get('items') or []), normalized)
            return {
                **cached,
                'items': items,
                'source': _payload_source(items) if items else cached.get('source'),
                'cached': True,
            }
        items = await asyncio.to_thread(cls._fetch_items, normalized)
        payload = {
            'items': items,
            'asOf': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            'source': _payload_source(items),
        }
        if items:
            await cache_set_json(cache_key, payload, CACHE_TTL_SECONDS)
        items = _overlay_hub_quotes(items, normalized)
        return {**payload, 'items': items, 'source': _payload_source(items) if items else payload['source'], 'cached': False}

    @classmethod
    def _fetch_items(cls, pairs: list[tuple[str, str]]) -> list[dict[str, Any]]:
        try:
            live_pairs, rest_pairs = _partition_live_pairs(pairs)
            by_key: dict[tuple[str, str], dict[str, Any]] = {}
            for item in _overlay_hub_quotes([], live_pairs):
                by_key[(item['symbol'], item['market'])] = item
            missing_live = [pair for pair in live_pairs if pair not in by_key]
            for item in _fetch_longbridge_items(missing_live):
                by_key[(item['symbol'], item['market'])] = item
            missing = [pair for pair in live_pairs if pair not in by_key]
            tencent_pairs = rest_pairs + missing
            if tencent_pairs:
                for item in _fetch_tencent_items(tencent_pairs):
                    by_key.setdefault((item['symbol'], item['market']), item)
            return [by_key[pair] for pair in pairs if pair in by_key]
        except Exception as exc:
            logger.warning(f'[live-quotes] 混合拉取失败，回退腾讯: {exc}')
            try:
                return _fetch_tencent_items(pairs)
            except Exception as fallback_exc:
                logger.warning(f'[live-quotes] 腾讯回退失败: {fallback_exc}')
                return []
