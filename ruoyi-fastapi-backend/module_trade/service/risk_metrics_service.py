"""持仓组合收益指标（QuantStats / empyrical 风格，纯 pandas/numpy，不引入新依赖）。"""

from __future__ import annotations

import asyncio
import math
from typing import TYPE_CHECKING, Any

from module_market.service.live_quotes_service import normalize_symbol_market
from module_trade.service.auto_trade_service import existing_position_market_value
from module_trade.service.trade_service import TradeService
from utils.influx_util import InfluxUtil
from utils.log_util import logger

TRADING_DAYS = 252
MIN_RETURNS = 20
DEFAULT_DAYS = 120
MAX_POSITIONS = 20

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def daily_returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    prev: float | None = None
    for price in closes:
        px = _finite(price)
        if prev and prev > 0 and px > 0:
            out.append(px / prev - 1.0)
        if px > 0:
            prev = px
    return out


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for ret in returns:
        equity *= 1.0 + ret
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, equity / peak - 1.0)
    return worst


def compute_metrics(returns: list[float]) -> dict[str, float | None]:
    n = len(returns)
    if n < MIN_RETURNS:
        return {
            'days': n,
            'sharpe': None,
            'sortino': None,
            'maxDrawdown': None,
            'var95': None,
            'cvar95': None,
            'volatility': None,
            'totalReturn': None,
        }
    mean = sum(returns) / n
    var = sum((item - mean) ** 2 for item in returns) / n
    sigma = math.sqrt(var)
    downside = [item for item in returns if item < 0]
    down_var = sum(item * item for item in downside) / n if downside else 0.0
    down_sigma = math.sqrt(down_var)
    ordered = sorted(returns)
    idx = max(0, min(n - 1, int(n * 0.05)))
    var95 = ordered[idx]
    tail = ordered[: idx + 1] or [var95]
    total = 1.0
    for item in returns:
        total *= 1.0 + item
    return {
        'days': n,
        'sharpe': None if sigma <= 0 else round(mean / sigma * math.sqrt(TRADING_DAYS), 4),
        'sortino': None if down_sigma <= 0 else round(mean / down_sigma * math.sqrt(TRADING_DAYS), 4),
        'maxDrawdown': round(max_drawdown(returns), 4),
        'var95': round(var95, 6),
        'cvar95': round(sum(tail) / len(tail), 6),
        'volatility': round(sigma * math.sqrt(TRADING_DAYS), 4),
        'totalReturn': round(total - 1.0, 4),
    }


def _weighted_returns(series: dict[str, list[float]], weights: dict[str, float]) -> list[float]:
    if not series or not weights:
        return []
    length = min(len(vals) for vals in series.values() if vals)
    if length < MIN_RETURNS:
        return []
    total_w = sum(weights.get(key, 0.0) for key in series)
    if total_w <= 0:
        return []
    out: list[float] = []
    for i in range(length):
        acc = 0.0
        for key, vals in series.items():
            w = weights.get(key, 0.0)
            if w <= 0 or i >= len(vals):
                continue
            acc += (w / total_w) * vals[i]
        out.append(acc)
    return out


class RiskMetricsService:
    """按当前长桥持仓权重，用 Influx 日 K 拼组合收益。"""

    @classmethod
    async def get_tearsheet_services(
        cls,
        query_db: AsyncSession,
        *,
        days: int = DEFAULT_DAYS,
    ) -> dict[str, Any]:
        window = max(40, min(int(days or DEFAULT_DAYS), 400))
        data = await TradeService.get_positions_services(query_db)
        positions = list(data.get('positions') or [])
        if not positions:
            return {
                **compute_metrics([]),
                'positions': 0,
                'configured': data.get('configured'),
                'message': data.get('message') or '当前没有持仓，无法计算组合指标',
            }

        weights: dict[str, float] = {}
        markets: dict[str, str] = {}
        names: dict[str, str] = {}
        for pos in positions[:MAX_POSITIONS]:
            pair = normalize_symbol_market(str(pos.get('symbol') or ''), None)
            if not pair:
                continue
            symbol, market = pair
            last = _finite(pos.get('last'))
            mv = existing_position_market_value(pos, last)
            if mv <= 0:
                continue
            weights[symbol] = weights.get(symbol, 0.0) + mv
            markets[symbol] = market
            names[symbol] = str(pos.get('symbolName') or pos.get('name') or symbol)

        if len(weights) < 1:
            return {
                **compute_metrics([]),
                'positions': len(positions),
                'message': '持仓缺少市值/价格，无法计算',
            }

        by_market: dict[str, list[str]] = {}
        for symbol, market in markets.items():
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
                logger.warning(f'[tearsheet] Influx 失败 market={market}: {exc}')
                return {}

        groups = await asyncio.gather(*[_pull(market, symbols) for market, symbols in by_market.items()])
        series: dict[str, list[float]] = {}
        for group in groups:
            for symbol, bars in (group or {}).items():
                closes = [_finite(bar.get('close')) for bar in bars or []]
                closes = [px for px in closes if px > 0]
                rets = daily_returns(closes)
                if len(rets) >= MIN_RETURNS:
                    series[symbol] = rets[-window:]

        port = _weighted_returns(series, weights)
        metrics = compute_metrics(port)
        covered = [key for key in weights if key in series]
        return {
            **metrics,
            'positions': len(weights),
            'covered': len(covered),
            'names': [names.get(key, key) for key in covered],
            'weights': {key: round(weights[key] / sum(weights.values()), 4) for key in covered},
            'message': '' if covered else '持仓日 K 不足，无法计算组合指标',
        }
