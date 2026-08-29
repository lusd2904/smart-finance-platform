"""把市场简报 / 舆情标题绑定到具体标的代码与名称。"""

from __future__ import annotations

import json
import re
from typing import Any

_TOKEN_RE_CACHE: dict[str, re.Pattern[str]] = {}
_ASCII_NAME_MIN = 3
_CJK_NAME_MIN = 2
_SHORT_TICKER = 2
_DIGIT_TICKER_MIN = 3


def symbol_aliases(symbol: str, market: str = 'US') -> list[str]:
    raw = str(symbol or '').strip().upper()
    mkt = str(market or 'US').strip().upper()
    if not raw:
        return []
    if '.' in raw:
        raw, suffix = raw.rsplit('.', 1)
        if suffix in {'US', 'HK', 'SH', 'SZ', 'SS'}:
            mkt = 'US' if suffix == 'US' else 'HK' if suffix == 'HK' else 'CN'
    aliases = [raw]
    if mkt == 'US':
        aliases.append(f'{raw}.US')
    elif mkt == 'HK':
        aliases.extend([f'{raw}.HK', raw.lstrip('0') or '0'])
        if raw.isdigit():
            aliases.append(raw.zfill(5))
            aliases.append(f'{(raw.lstrip("0") or "0")}.HK')
    elif mkt == 'CN':
        aliases.extend([f'{raw}.SH', f'{raw}.SZ', f'{raw}.SS'])
    out: list[str] = []
    seen: set[str] = set()
    for item in aliases:
        key = item.upper()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _token_pattern(alias: str) -> re.Pattern[str]:
    cached = _TOKEN_RE_CACHE.get(alias)
    if cached is not None:
        return cached
    escaped = re.escape(alias)
    if alias.isdigit() or alias.replace('.', '', 1).isdigit():
        pattern = re.compile(rf'(?<!\d){escaped}(?!\d)', re.IGNORECASE)
    else:
        pattern = re.compile(rf'(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])', re.IGNORECASE)
    _TOKEN_RE_CACHE[alias] = pattern
    return pattern


def _usable_ticker(alias: str) -> bool:
    core = alias.split('.', 1)[0]
    if core.isdigit():
        return len(core) >= _DIGIT_TICKER_MIN
    return len(core) > _SHORT_TICKER or '.' in alias


def text_mentions_symbol(text: str, symbol: str, market: str = 'US', name: str | None = None) -> bool:
    blob = str(text or '').strip()
    if not blob:
        return False
    for alias in symbol_aliases(symbol, market):
        if not _usable_ticker(alias):
            continue
        if _token_pattern(alias).search(blob):
            return True
    label = str(name or '').strip()
    if not label:
        return False
    if re.search(r'[\u4e00-\u9fff]', label):
        return len(label) >= _CJK_NAME_MIN and label in blob
    if len(label) < _ASCII_NAME_MIN:
        return False
    return _token_pattern(label.upper()).search(blob.upper()) is not None


async def related_news_items(
    db: Any,
    symbol: str,
    market: str = 'US',
    *,
    name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """从财经简报和舆情标题里捞出提到该标的的条目。失败空列表。"""
    from sqlalchemy import desc, select

    from module_market.dao.market_dao import FinanceBriefingDao, MarketInstrumentDao
    from module_sentiment.entity.do.sentiment_do import SentimentNews

    symbol = str(symbol or '').strip().upper()
    market = str(market or 'US').strip().upper()
    limit = max(1, min(int(limit or 20), 40))
    if not symbol:
        return []
    label = str(name or '').strip() or None
    if not label:
        try:
            row = await MarketInstrumentDao.get_by_symbol(db, symbol)
            label = (row.name if row else None) or None
        except Exception:
            label = None
    items: list[dict[str, Any]] = []
    try:
        briefings = await FinanceBriefingDao.get_latest(db, limit=40, market=market)
    except Exception:
        briefings = []
    for row in briefings:
        payload = {}
        try:
            raw = getattr(row, 'payload_json', None)
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {}
        codes = payload_symbols(payload)
        blob = f'{row.headline or ""} {row.summary or ""}'
        hit = symbol in codes or text_mentions_symbol(blob, symbol, market, label)
        if not hit:
            continue
        items.append(
            {
                'id': f'briefing:{row.id}',
                'symbol': symbol,
                'market': market,
                'contentType': 'news',
                'sourceName': row.source_name or 'briefing',
                'sourceItemId': str(row.id),
                'title': row.headline,
                'summary': (row.summary or '')[:500],
                'content': row.summary or '',
                'sourceLink': row.source_link,
                'publishedAt': row.generated_at.strftime('%Y-%m-%d %H:%M:%S') if row.generated_at else None,
                'fetchedAt': None,
                'bind': 'briefing',
                'symbols': codes or [symbol],
            }
        )
    try:
        news_rows = (
            await db.execute(select(SentimentNews).order_by(desc(SentimentNews.pub_time)).limit(50))
        ).scalars().all()
    except Exception:
        news_rows = []
    for row in news_rows:
        blob = f'{row.title or ""} {row.content or ""}'
        if not text_mentions_symbol(blob, symbol, market, label):
            continue
        published = row.pub_time or row.create_time
        items.append(
            {
                'id': f'sentiment:{row.news_id}',
                'symbol': symbol,
                'market': market,
                'contentType': 'news',
                'sourceName': row.source or 'sentiment',
                'sourceItemId': str(row.news_id),
                'title': row.title,
                'summary': (row.content or '')[:500],
                'content': row.content or '',
                'sourceLink': row.url,
                'publishedAt': published.strftime('%Y-%m-%d %H:%M:%S') if published else None,
                'fetchedAt': None,
                'bind': 'sentiment',
                'symbols': [symbol],
            }
        )
    items.sort(key=lambda item: str(item.get('publishedAt') or ''), reverse=True)
    return items[:limit]


def payload_symbols(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get('symbol') or payload.get('symbols') or payload.get('code')
    if isinstance(raw, str):
        code = raw.strip().upper()
        return [code] if code else []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            code = str(item or '').strip().upper()
            if code:
                out.append(code)
        return out
    return []
