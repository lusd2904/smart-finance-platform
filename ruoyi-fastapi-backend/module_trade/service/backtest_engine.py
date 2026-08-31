"""多空一档回测：用现有 8 族因子信号代替 MA 金叉。"""

from __future__ import annotations

from typing import Any

from module_quant.service.factor_service import FactorService
from module_quant.service.strategy_service import decide_signal

LOOKBACK = 30
DEFAULT_FEE = 0.0005
DEFAULT_SLIP = 0.0002


def simulate_long_only(
    klines: list[dict[str, Any]],
    signals: list[str],
    *,
    initial_capital: float = 100000.0,
    fee_rate: float = DEFAULT_FEE,
    slippage: float = DEFAULT_SLIP,
) -> dict[str, Any]:
    """按逐日 BUY/SELL/HOLD 做多：买入用光现金，卖出清仓。"""
    n = min(len(klines), len(signals))
    cash = float(initial_capital)
    pos = 0.0
    trades = 0
    round_trips = 0
    winning = 0
    last_buy = 0.0
    peak = float(initial_capital)
    max_dd = 0.0
    equity_curve: list[dict[str, Any]] = []
    last_close = 0.0

    for i in range(n):
        price = float(klines[i].get('close') or 0)
        if price <= 0:
            continue
        last_close = price
        sig = str(signals[i] or 'HOLD').upper()
        if sig == 'BUY' and pos <= 0 and cash > 0:
            exec_price = price * (1 + slippage)
            cost = exec_price * (1 + fee_rate)
            pos = cash / cost
            last_buy = exec_price
            cash = 0.0
            trades += 1
        elif sig == 'SELL' and pos > 0:
            exec_price = price * (1 - slippage)
            cash = pos * exec_price * (1 - fee_rate)
            round_trips += 1
            if exec_price > last_buy:
                winning += 1
            pos = 0.0
            trades += 1

        equity = cash + pos * price
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
        equity_curve.append({'date': klines[i].get('date'), 'equity': round(equity, 2), 'signal': sig})

    final_equity = cash + pos * last_close
    win_rate = round((winning / round_trips) * 100, 2) if round_trips else 0.0
    return {
        'ok': True,
        'trades': trades,
        'roundTrips': round_trips,
        'returnPct': round((final_equity / initial_capital - 1) * 100, 2) if initial_capital else 0.0,
        'finalEquity': round(final_equity, 2),
        'maxDrawdown': round(max_dd * 100, 2),
        'winRate': win_rate,
        'equity': equity_curve,
    }


def factor_signals(
    klines: list[dict[str, Any]],
    *,
    profile: str = 'balanced',
    weights: dict[str, Any] | None = None,
    lookback: int = LOOKBACK,
) -> list[str]:
    """对每个交易日用截至当日的 8 族因子决策。lookback 之前为 HOLD。一次算完整序列。"""
    out = ['HOLD'] * len(klines)
    start = max(int(lookback), 20)
    scores = FactorService.compute_score_series(klines, profile, weights)
    for i in range(start, len(klines)):
        score = scores[i] if i < len(scores) else None
        if not score:
            continue
        decision = decide_signal(score, profile, custom_thresholds=weights)
        out[i] = str(decision.get('signal') or 'HOLD').upper()
    return out
