"""自选收益相关矩阵。用现有 Influx 日 K，不引入新数据源。"""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING, Any

from module_market.dao.market_dao import MarketWatchlistDao
from module_market.service.live_quotes_service import normalize_symbol_market
from utils.influx_util import InfluxUtil
from utils.log_util import logger

MAX_SYMBOLS = 16
MIN_OVERLAP = 20
DEFAULT_DAYS = 60
MIN_SYMBOLS = 2

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _closes_by_date(bars: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for bar in bars or []:
        day = str(bar.get('date') or '')[:10]
        try:
            close = float(bar.get('close'))
        except (TypeError, ValueError):
            continue
        if day and math.isfinite(close) and close > 0:
            out[day] = close
    return out


def aligned_returns(series: dict[str, dict[str, float]]) -> dict[str, list[float]]:
    """按共同交易日对齐，返回各标的日收益。"""
    if not series:
        return {}
    common: set[str] | None = None
    for closes in series.values():
        keys = set(closes)
        common = keys if common is None else common & keys
    if not common:
        return {}
    days = sorted(common)
    if len(days) < MIN_OVERLAP + 1:
        return {}
    returns: dict[str, list[float]] = {}
    for symbol, closes in series.items():
        vals: list[float] = []
        prev: float | None = None
        for day in days:
            price = closes[day]
            if prev and prev > 0:
                vals.append(price / prev - 1.0)
            prev = price
        if len(vals) >= MIN_OVERLAP:
            returns[symbol] = vals
    return returns


def pearson(left: list[float], right: list[float]) -> float | None:
    n = min(len(left), len(right))
    if n < MIN_OVERLAP:
        return None
    xs = left[:n]
    ys = right[:n]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = 0.0
    var_x = 0.0
    var_y = 0.0
    for x, y in zip(xs, ys, strict=False):
        dx = x - mean_x
        dy = y - mean_y
        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def correlation_matrix(returns: dict[str, list[float]], labels: list[str]) -> list[list[float | None]]:
    matrix: list[list[float | None]] = []
    for row_key in labels:
        row: list[float | None] = []
        for col_key in labels:
            if row_key == col_key:
                row.append(1.0)
                continue
            left = returns.get(row_key)
            right = returns.get(col_key)
            if not left or not right:
                row.append(None)
                continue
            value = pearson(left, right)
            row.append(None if value is None else round(value, 4))
        matrix.append(row)
    return matrix


class WatchlistCorrelationService:
    """当前用户自选的收益相关热力。"""

    @classmethod
    async def get_correlation_services(
        cls,
        query_db: AsyncSession,
        user_id: int,
        *,
        days: int = DEFAULT_DAYS,
        limit: int = MAX_SYMBOLS,
    ) -> dict[str, Any]:
        if not user_id:
            return {'symbols': [], 'names': [], 'matrix': [], 'message': '无法识别当前用户'}
        cap = max(2, min(int(limit or MAX_SYMBOLS), MAX_SYMBOLS))
        window = max(30, min(int(days or DEFAULT_DAYS), 250))
        rows = await MarketWatchlistDao.get_enabled(query_db, user_id=user_id)
        picked: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for row in rows:
            pair = normalize_symbol_market(row.symbol, row.market)
            if not pair:
                continue
            symbol, market = pair
            key = f'{symbol}:{market}'
            if key in seen:
                continue
            seen.add(key)
            picked.append((symbol, market, str(getattr(row, 'name', None) or symbol)))
            if len(picked) >= cap:
                break
        if len(picked) < MIN_SYMBOLS:
            return {
                'symbols': [item[0] for item in picked],
                'names': [item[2] for item in picked],
                'markets': [item[1] for item in picked],
                'matrix': [],
                'days': window,
                'message': '至少两只自选才能计算相关',
            }

        by_market: dict[str, list[str]] = {}
        for symbol, market, _name in picked:
            by_market.setdefault(market, []).append(symbol)

        async def _pull(market: str, symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
            try:
                return await asyncio.to_thread(
                    InfluxUtil.query_klines_many,
                    market,
                    symbols,
                    f'-{window + 20}d',
                    window + 5,
                )
            except Exception as exc:
                logger.warning(f'[correlation] Influx 失败 market={market}: {exc}')
                return {}

        groups = await asyncio.gather(*[_pull(market, symbols) for market, symbols in by_market.items()])
        series: dict[str, dict[str, float]] = {}
        for group in groups:
            for symbol, bars in (group or {}).items():
                closes = _closes_by_date(bars)
                if closes:
                    series[symbol] = closes

        labels = [symbol for symbol, _market, _name in picked if symbol in series]
        names = [name for symbol, _market, name in picked if symbol in series]
        markets = [market for symbol, market, _name in picked if symbol in series]
        returns = aligned_returns({key: series[key] for key in labels})
        usable = [key for key in labels if key in returns]
        if len(usable) < MIN_SYMBOLS:
            return {
                'symbols': labels,
                'names': names,
                'markets': markets,
                'matrix': [],
                'days': window,
                'message': '重叠交易日不足，无法计算相关',
            }
        name_map = dict(zip(labels, names, strict=False))
        market_map = dict(zip(labels, markets, strict=False))
        return {
            'symbols': usable,
            'names': [name_map.get(key, key) for key in usable],
            'markets': [market_map.get(key, 'US') for key in usable],
            'matrix': correlation_matrix(returns, usable),
            'days': window,
            'overlap': min(len(returns[key]) for key in usable),
            'message': '',
        }
