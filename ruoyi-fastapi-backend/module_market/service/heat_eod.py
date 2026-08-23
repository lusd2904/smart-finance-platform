"""
Public EOD heat / Top50 collector.

Uses sina (US) and tencent/eastmoney (CN/HK). Never calls Longbridge.
Does not wipe existing Top50 rows when a later collect returns 0.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from module_market.config.heat_config import MARKET_META
from module_market.dao.heat_dao import MarketHeatDao
from module_market.service.heat_service import (
    MarketHeatService,
    _heat_summary,
    _is_weekday,
    _normalize_market,
    _resolve_trade_date,
)
from utils.log_util import logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

UA = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn',
}


def _http_get(url: str, timeout: int = 20, encoding: str = 'utf-8') -> str:
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            req = Request(url, headers=UA)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            for enc in (encoding, 'utf-8', 'gbk'):
                try:
                    return raw.decode(enc)
                except Exception:  # noqa: PERF203 - 多编码逐个尝试
                    continue
            return raw.decode('utf-8', 'replace')
        except Exception as exc:
            last_err = exc
            logger.warning(f'[heat_eod] GET fail attempt={attempt+1} url={url[:120]} err={exc}')
    raise last_err or RuntimeError(f'GET failed {url}')


def _safe_call(name: str, fn: Any, *args: Any, default: Any = None, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning(f'[heat_eod] {name} failed: {exc}')
        if default is not None:
            return default
        return [] if 'rank' in name or 'amount' in name else {}


def _to_float(value: Any) -> float | None:
    if value is None or value in {'', '-'}:
        return None
    try:
        return float(str(value).replace(',', '').replace('%', ''))
    except (TypeError, ValueError):
        return None


def _fetch_tencent_quote(code: str) -> dict[str, Any]:
    text = _http_get(f'https://qt.gtimg.cn/q={code}', encoding='gbk')
    m = re.search(r'="([^"]*)"', text)
    if not m:
        return {}
    parts = m.group(1).split('~')
    # 腾讯行情字段索引：3=现价 4=昨收 32=涨跌幅 37=成交额(元) 36=成交额(手)
    idx_last, idx_prev, idx_chg, idx_amt, idx_amt_fb, min_parts = 3, 4, 32, 37, 36, 6
    amount_small_threshold = 1e8
    if len(parts) < min_parts:
        return {}
    last = _to_float(parts[idx_last])
    prev = _to_float(parts[idx_prev])
    change_pct = None
    if len(parts) > idx_chg:
        change_pct = _to_float(parts[idx_chg])
    if change_pct is None and last and prev:
        change_pct = round((last / prev - 1.0) * 100, 4)
    turnover = None
    if len(parts) > idx_amt:
        turnover = _to_float(parts[idx_amt])
        if turnover is not None and turnover < amount_small_threshold and last:
            turnover = _to_float(parts[idx_amt_fb])
    return {
        'name': parts[1],
        'last': last,
        'prev': prev,
        'change_pct': change_pct,
        'turnover': turnover,
        'raw_len': len(parts),
    }


def _fetch_eastmoney_index(secid: str) -> dict[str, Any]:
    qs = urlencode(
        {
            'fltt': '2',
            'secids': secid,
            'fields': 'f3,f6,f14,f104,f105,f106',
        }
    )
    payload = json.loads(_http_get(f'https://push2.eastmoney.com/api/qt/ulist.np/get?{qs}'))
    rows = ((payload.get('data') or {}).get('diff') or [])
    if not rows:
        return {}
    row = rows[0]
    return {
        'name': row.get('f14'),
        'change_pct': _to_float(row.get('f3')),
        'turnover': _to_float(row.get('f6')),
        'advance': int(row.get('f104') or 0),
        'decline': int(row.get('f105') or 0),
        'flat': int(row.get('f106') or 0),
    }


def _fetch_eastmoney_rank(fs: str, pages: int = 1, page_size: int = 80) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        qs = urlencode(
            {
                'pn': page,
                'pz': page_size,
                'po': 1,
                'np': 1,
                'fltt': 2,
                'invt': 2,
                'fs': fs,
                'fid': 'f6',
                'fields': 'f12,f14,f2,f3,f6,f20',
            }
        )
        payload = json.loads(_http_get(f'https://push2.eastmoney.com/api/qt/clist/get?{qs}'))
        rows = ((payload.get('data') or {}).get('diff') or [])
        if not rows:
            break
        for row in rows:
            cap = _to_float(row.get('f20'))
            turnover = _to_float(row.get('f6'))
            out.append(
                {
                    'symbol': str(row.get('f12') or ''),
                    'name': str(row.get('f14') or row.get('f12') or ''),
                    'market_cap': cap,
                    'turnover': turnover,
                    'change_pct': _to_float(row.get('f3')),
                }
            )
    return out


def _fetch_sina_cn_rank(pages: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        qs = urlencode(
            {
                'page': page,
                'num': 80,
                'sort': 'amount',
                'asc': 0,
                'node': 'hs_a',
            }
        )
        text = _http_get(
            'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
            f'Market_Center.getHQNodeData?{qs}'
        )
        rows = json.loads(text or '[]')
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            cap = _to_float(row.get('mktcap'))
            cap_unit_threshold = 1e11  # 新浪该接口万元单位判定阈值
            if cap is not None and cap < cap_unit_threshold:
                cap = cap * 10000.0
            out.append(
                {
                    'symbol': str(row.get('code') or row.get('symbol') or ''),
                    'name': str(row.get('name') or ''),
                    'market_cap': cap,
                    'turnover': _to_float(row.get('amount')),
                    'change_pct': _to_float(row.get('changepercent')),
                }
            )
    return out


def _fetch_sina_hk_rank(pages: int = 3) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        qs = urlencode(
            {
                'page': page,
                'num': 80,
                'sort': 'amount',
                'asc': 0,
                'node': 'qbgg_hk',
            }
        )
        text = _http_get(
            'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
            f'Market_Center.getHKStockData?{qs}'
        )
        rows = json.loads(text or '[]')
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            cap = _to_float(row.get('market_value'))
            out.append(
                {
                    'symbol': str(row.get('symbol') or ''),
                    'name': str(row.get('name') or row.get('engname') or ''),
                    'market_cap': cap if cap and cap > 0 else None,
                    'turnover': _to_float(row.get('amount')),
                    'change_pct': _to_float(row.get('changepercent')),
                }
            )
    return out


def _extract_jsonp(text: str) -> Any:
    start = text.find('(')
    end = text.rfind(')')
    if start < 0 or end <= start:
        raise ValueError('jsonp payload missing')
    return json.loads(text[start + 1 : end])


def _fetch_sina_us_rank(pages: int = 6, sort: str = 'volume') -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        qs = urlencode(
            {
                'page': page,
                'num': 80,
                'sort': sort,
                'asc': 0,
                'market': '',
                'id': '',
            }
        )
        text = _http_get(
            'https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20xx=/'
            f'US_CategoryService.getList?{qs}'
        )
        payload = _extract_jsonp(text)
        rows = payload.get('data') if isinstance(payload, dict) else payload
        if not rows:
            break
        for row in rows:
            price = _to_float(row.get('price'))
            volume = _to_float(row.get('volume'))
            amount = _to_float(row.get('amount'))
            if amount is None and price and volume:
                amount = price * volume
            out.append(
                {
                    'symbol': str(row.get('symbol') or '').upper(),
                    'name': str(row.get('cname') or row.get('name') or ''),
                    'market_cap': _to_float(row.get('mktcap')),
                    'turnover': amount,
                    'change_pct': _to_float(row.get('chg')),
                }
            )
    return out


def _merge_candidates(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            symbol = str(item.get('symbol') or '').strip()
            if not symbol:
                continue
            key = symbol.upper()
            current = by_symbol.get(key)
            if current is None:
                by_symbol[key] = dict(item)
                continue
            for field in ('name', 'market_cap', 'turnover', 'change_pct'):
                if current.get(field) in (None, '', 0) and item.get(field) not in (None, ''):
                    current[field] = item[field]
            if item.get('turnover') and (current.get('turnover') or 0) < item['turnover']:
                current['turnover'] = item['turnover']
    return list(by_symbol.values())


_BREADTH_FLAT_BAND_PCT = 0.05


def _count_breadth(candidates: list[dict[str, Any]]) -> tuple[int, int, int]:
    advance = decline = flat = 0
    band = _BREADTH_FLAT_BAND_PCT
    for item in candidates:
        change = item.get('change_pct')
        if change is None:
            continue
        if change > band:
            advance += 1
        elif change < -band:
            decline += 1
        else:
            flat += 1
    return advance, decline, flat


def _public_universe(market: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    extras: dict[str, Any] = {'source': []}
    if market == 'CN':
        tencent = _safe_call('tencent-index', _fetch_tencent_quote, 'sh000001')
        em_index = _safe_call('em-index', _fetch_eastmoney_index, '1.000001')
        sina_rows = _safe_call('sina-cn-rank', _fetch_sina_cn_rank)
        em_rows = _safe_call('em-cn-rank', _fetch_eastmoney_rank, 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23')
        extras['source'] = ['tencent-index', 'sina-rank', 'eastmoney-rank']
        extras['index_change'] = em_index.get('change_pct') or tencent.get('change_pct')
        extras['advance'] = em_index.get('advance')
        extras['decline'] = em_index.get('decline')
        extras['flat'] = em_index.get('flat')
        extras['index_turnover'] = em_index.get('turnover') or tencent.get('turnover')
        return _merge_candidates(em_rows, sina_rows), extras
    if market == 'HK':
        tencent = _safe_call('tencent-hk-index', _fetch_tencent_quote, 'r_hkHSI')
        em_index = _safe_call('em-hk-index', _fetch_eastmoney_index, '116.HSI')
        sina_rows = _safe_call('sina-hk-rank', _fetch_sina_hk_rank)
        em_rows = _safe_call('em-hk-rank', _fetch_eastmoney_rank, 'm:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2')
        extras['source'] = ['tencent-index', 'sina-rank', 'eastmoney-rank']
        extras['index_change'] = tencent.get('change_pct') or em_index.get('change_pct')
        extras['advance'] = em_index.get('advance')
        extras['decline'] = em_index.get('decline')
        extras['flat'] = em_index.get('flat')
        extras['index_turnover'] = tencent.get('turnover') or em_index.get('turnover')
        return _merge_candidates(em_rows, sina_rows), extras
    sina_rows = _safe_call('sina-us-rank', _fetch_sina_us_rank, sort='volume')
    sina_amt = _safe_call('sina-us-amount', _fetch_sina_us_rank, pages=3, sort='amount')
    em_index = _safe_call('em-us-index', _fetch_eastmoney_index, '100.SPX')
    extras['source'] = ['sina-us', 'eastmoney-index']
    extras['index_change'] = em_index.get('change_pct')
    extras['advance'] = em_index.get('advance')
    extras['decline'] = em_index.get('decline')
    extras['flat'] = em_index.get('flat')
    return _merge_candidates(sina_rows, sina_amt), extras


async def collect_market(db: AsyncSession, market: str, trade_date: str | None = None) -> dict[str, Any]:
    market = _normalize_market(market)
    session_date = _resolve_trade_date(market, trade_date)
    if not _is_weekday(session_date):
        return {'skipped': True, 'market': market, 'tradeDate': session_date, 'reason': 'non_trading_day'}

    meta = MARKET_META[market]
    weights = await MarketHeatService.resolve_weights()
    # _public_universe 内部为同步 urllib 多页 HTTP，放线程池执行避免阻塞事件循环
    candidates, extras = await asyncio.to_thread(_public_universe, market)
    if not candidates:
        existing = await MarketHeatDao.list_top50(db, market, session_date)
        return {
            'skipped': True,
            'market': market,
            'tradeDate': session_date,
            'reason': 'public_eod_empty',
            'keptExistingTop50': len(existing or []),
        }

    for item in candidates:
        item['currency'] = meta['currency']

    sample_adv, sample_dec, sample_flat = _count_breadth(candidates)
    advance = extras.get('advance') or 0
    decline = extras.get('decline') or 0
    flat = extras.get('flat') or 0
    if advance + decline <= 0:
        advance, decline, flat = sample_adv, sample_dec, sample_flat

    total_turnover = sum(float(item['turnover']) for item in candidates if item.get('turnover'))
    if extras.get('index_turnover'):
        total_turnover = max(total_turnover, float(extras['index_turnover']))

    index_change = extras.get('index_change')
    trend_rows = await MarketHeatDao.list_heat_trend(db, market, limit=5)
    baseline = None
    if trend_rows:
        vals = [float(r.total_turnover) for r in trend_rows if r.total_turnover]
        baseline = sum(vals) / len(vals) if vals else None

    top50 = MarketHeatService.filter_top50_candidates(market, candidates)
    fallback = False
    if not top50:
        ranked = [c for c in candidates if c.get('turnover')]
        ranked.sort(key=lambda x: float(x.get('turnover') or 0), reverse=True)
        loose_min = float(meta['cap_min']) * 0.2
        loose_max = float(meta['cap_max']) * 5
        loose = [
            c
            for c in ranked
            if c.get('market_cap') and loose_min <= float(c['market_cap']) <= loose_max
        ]
        with_cap = [c for c in ranked if c.get('market_cap')]
        pick = (loose or with_cap or ranked)[:50]
        for idx, item in enumerate(pick, start=1):
            item['rankNo'] = idx
        top50 = pick
        fallback = True
        logger.warning(f'[heat_eod] {market} official cap-filter empty; fallback top50={len(top50)}')
    if not top50:
        existing = await MarketHeatDao.list_top50(db, market, session_date)
        logger.warning(f'[heat_eod] {market} still empty; keep existing={len(existing or [])}')
        return {
            'skipped': True,
            'market': market,
            'tradeDate': session_date,
            'reason': 'cap_filter_empty',
            'candidateCount': len(candidates),
            'keptExistingTop50': len(existing or []),
        }

    heat_score = MarketHeatService.compute_heat_score(
        weights, index_change, total_turnover, advance, decline, baseline
    )
    summary = _heat_summary(heat_score, market, index_change, advance, decline)
    as_of = datetime.now()
    await MarketHeatDao.upsert_heat(
        db,
        {
            'market': market,
            'trade_date': session_date,
            'index_symbol': meta['index_symbol'],
            'index_name': meta['index_name'],
            'index_change_pct': index_change,
            'total_turnover': total_turnover or None,
            'advance_count': advance,
            'decline_count': decline,
            'flat_count': flat,
            'heat_score': heat_score,
            'heat_summary': summary,
            'currency': meta['currency'],
            'filter_rule': meta['cap_rule'],
            'weights_json': json.dumps(weights, ensure_ascii=False),
            'as_of_time': as_of,
            'status': 'ok',
            'message': f"public eod {','.join(extras.get('source') or [])}{' fallback' if fallback else ''}",
            'create_time': as_of,
            'update_time': as_of,
        },
    )
    await MarketHeatDao.replace_top50(
        db,
        market,
        session_date,
        [
            {
                'market': market,
                'trade_date': session_date,
                'rank_no': item['rankNo'],
                'symbol': item['symbol'],
                'name': item['name'],
                'market_cap': item['market_cap'],
                'turnover': item['turnover'],
                'change_pct': item['change_pct'],
                'currency': item['currency'],
                'as_of_time': as_of,
                'create_time': as_of,
            }
            for item in top50
        ],
    )
    await db.commit()
    result = {
        'market': market,
        'tradeDate': session_date,
        'heatScore': heat_score,
        'top50Count': len(top50),
        'candidateCount': len(candidates),
        'status': 'ok',
        'source': extras.get('source'),
        'asOfTime': as_of.strftime('%Y-%m-%d %H:%M:%S'),
    }
    logger.info(f'[heat_eod] done {result}')
    return result


async def collect_all(markets: list[str] | None = None) -> list[dict[str, Any]]:
    from config.database import AsyncSessionLocal

    results = []
    async with AsyncSessionLocal() as db:
        for market in markets or ['CN', 'HK', 'US']:
            try:
                results.append(await collect_market(db, market))
            except Exception as exc:  # noqa: PERF203 - 单市场失败不中断其余市场
                logger.exception(f'[heat_eod] {market} failed')
                results.append({'market': market, 'status': 'error', 'error': str(exc)})
    return results


if __name__ == '__main__':
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description='Public EOD heat collector')
    parser.add_argument('markets', nargs='*', default=['CN', 'HK', 'US'])
    parser.add_argument('--env', default='dockersentiment')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(collect_all([m.upper() for m in args.markets])), ensure_ascii=False, indent=2))
