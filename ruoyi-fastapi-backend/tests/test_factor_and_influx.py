import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.factor_service import compute_alpha_factors
from module_quant.service.strategy_service import decide_signal
from utils.influx_util import _safe_symbol, _safe_time_clause


def test_influx_rejects_unsafe_params() -> None:
    assert _safe_symbol('AAPL') == 'AAPL'
    assert _safe_symbol("AAPL\"; drop") is None
    assert _safe_time_clause('-1y') == '-1y'
    assert _safe_time_clause('now()') == 'now()'
    assert _safe_time_clause('2024-01-01T00:00:00Z') is not None
    assert _safe_time_clause('1h; evil') is None


def test_alpha_factors_on_synthetic_klines() -> None:
    rows = []
    price = 100.0
    for i in range(40):
        price += 0.5 if i % 3 else -0.2
        rows.append(
            {
                'open': price - 0.3,
                'high': price + 0.6,
                'low': price - 0.7,
                'close': price,
                'volume': 1_000_000 + i * 1000,
            }
        )
    df = pd.DataFrame(rows)
    alphas = compute_alpha_factors(df)
    assert 'alpha006' in alphas
    assert 'alpha012' in alphas
    assert 'qlib_sharpe20' in alphas


def test_decide_signal_thresholds() -> None:
    buy = decide_signal({'total': 80, 'riskLevel': 'low', 'trendDirection': 'up', 'tags': ['强势']}, 'balanced')
    assert buy['signal'] == 'BUY'
    sell = decide_signal({'total': 20, 'riskLevel': 'high', 'trendDirection': 'down', 'tags': []}, 'balanced')
    assert sell['signal'] == 'SELL'
    hold = decide_signal({'total': 50, 'riskLevel': 'low', 'trendDirection': 'sideways', 'tags': []}, 'balanced')
    assert hold['signal'] == 'HOLD'
