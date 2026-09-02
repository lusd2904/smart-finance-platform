"""全市场智能选股：候选合并、打分与建议映射（无基础设施依赖）。"""

from __future__ import annotations

from typing import Any

INDEX_PREFIXES = ('^',)
SENTIMENT_FIELD = {'US': 'usScore', 'HK': 'hkScore', 'CN': 'aScore'}
CANDIDATE_CAP = 80
PICKS_PER_MARKET = 10
AI_PER_MARKET = 10
AI_CONCURRENCY = 2
BUY_SCORE_THRESHOLD = 62.0
WATCH_SCORE_THRESHOLD = 58.0


def clamp_score(value: float | None, default: float = 50.0) -> float:
    if value is None:
        return default
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, num))


def normalize_sentiment(raw: float | None) -> float:
    """对齐 Flutter `sentimentIndexTo100`：[-10,10] → (x+10)*5；已是 0–100 则原样夹紧。"""
    if raw is None:
        return 50.0
    try:
        num = float(raw)
    except (TypeError, ValueError):
        return 50.0
    if -10 <= num <= 10:
        return clamp_score((num + 10.0) * 5.0)
    return clamp_score(num)


def is_index_symbol(symbol: str | None, category: str | None = None) -> bool:
    code = (symbol or '').strip()
    if not code:
        return True
    if (category or '').lower() == 'index':
        return True
    return code.startswith(INDEX_PREFIXES)


def merge_candidates(
    top50: list[dict[str, Any]],
    featured: list[dict[str, Any]],
    cap: int = CANDIDATE_CAP,
) -> list[dict[str, Any]]:
    """Top50 优先，再补精选池，去重、跳过指数，每市场上限 cap。"""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in list(top50 or []) + list(featured or []):
        symbol = str(row.get('symbol') or '').strip()
        market = str(row.get('market') or 'US').strip().upper()
        if is_index_symbol(symbol, row.get('category')) or market not in {'US', 'HK', 'CN'}:
            continue
        key = (symbol.upper(), market)
        if key in seen:
            continue
        seen.add(key)
        item = dict(row)
        item['symbol'] = symbol
        item['market'] = market
        item['name'] = row.get('name') or symbol
        out.append(item)
        if len(out) >= cap:
            break
    return out


def combine_pick_score(
    factor_total: float | None,
    *,
    sentiment_raw: float | None = None,
    heat_score: float | None = None,
    index_open: bool = False,
    index_change_pct: float | None = None,
) -> float:
    """
    开盘：指标 + 舆情 + 收盘热度 + 实时指数。
    休市：去掉大盘指数，只用指标 + 舆情，保证仍能动态出单。
    """
    factor = clamp_score(factor_total, 0.0)
    sent = normalize_sentiment(sentiment_raw)
    if not index_open:
        return round(0.72 * factor + 0.28 * sent, 2)
    heat = clamp_score(heat_score)
    idx = 50.0
    if index_change_pct is not None:
        try:
            idx = clamp_score(50.0 + float(index_change_pct) * 8.0)
        except (TypeError, ValueError):
            idx = 50.0
    return round(0.55 * factor + 0.20 * sent + 0.15 * heat + 0.10 * idx, 2)


def reco_from_signal(signal: str | None, pick_score: float) -> tuple[str, str]:
    sig = (signal or 'HOLD').upper()
    if sig == 'BUY' and pick_score >= BUY_SCORE_THRESHOLD:
        return '买入', '偏多'
    if sig == 'BUY':
        return '关注', '偏多'
    if sig == 'SELL':
        return '回避', '偏空'
    if pick_score >= WATCH_SCORE_THRESHOLD:
        return '关注', '偏多'
    return '观望', '中性'


def select_top_picks(rows: list[dict[str, Any]], per_market: int = PICKS_PER_MARKET) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {'US': [], 'HK': [], 'CN': []}
    for row in rows:
        market = str(row.get('market') or '').upper()
        if market in buckets:
            buckets[market].append(row)
    picked: list[dict[str, Any]] = []
    for market, items in buckets.items():
        items.sort(
            key=lambda x: (1 if str(x.get('signal') or '').upper() == 'BUY' else 0, float(x.get('pickScore') or 0)),
            reverse=True,
        )
        for rank, item in enumerate(items[: max(1, per_market)], 1):
            row = dict(item)
            row['rankNo'] = rank
            row['market'] = market
            picked.append(row)
    picked.sort(key=lambda x: ({'CN': 0, 'HK': 1, 'US': 2}.get(x['market'], 9), x.get('rankNo') or 99))
    return picked


def ai_shortlist(rows: list[dict[str, Any]], per_market: int = AI_PER_MARKET) -> list[dict[str, Any]]:
    return select_top_picks(rows, per_market=per_market)


def apply_ai_result(row: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """把模型 JSON 写回选股行；缺字段保留规则结果。"""
    if not parsed:
        return row
    row['source'] = 'ai'
    if parsed.get('stance'):
        row['stance'] = str(parsed.get('stance'))
    if parsed.get('recommendation'):
        row['recommendation'] = str(parsed.get('recommendation'))
    if parsed.get('confidence') is not None:
        try:
            row['confidence'] = max(0, min(100, int(parsed.get('confidence'))))
        except (TypeError, ValueError):
            pass
    if parsed.get('summary'):
        row['summary'] = str(parsed.get('summary'))
    if parsed.get('indicator_review'):
        row['indicatorReview'] = str(parsed.get('indicator_review'))
    if parsed.get('sentiment_review'):
        row['sentimentReview'] = str(parsed.get('sentiment_review'))
    if parsed.get('operation_advice'):
        row['operationAdvice'] = str(parsed.get('operation_advice'))
    if parsed.get('risk_warning'):
        row['riskWarning'] = str(parsed.get('risk_warning'))
    return row
