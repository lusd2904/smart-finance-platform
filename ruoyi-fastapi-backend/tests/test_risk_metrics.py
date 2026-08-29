"""组合收益指标：Sharpe / 回撤 / VaR。"""

import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_trade.service.risk_metrics_service import compute_metrics, daily_returns, max_drawdown


def test_daily_returns_and_drawdown() -> None:
    closes = [100, 110, 99, 108]
    rets = daily_returns(closes)
    assert abs(rets[0] - 0.1) < 1e-9
    assert max_drawdown([0.1, -0.2, 0.05]) < 0
    assert max_drawdown([0.01, 0.02, 0.03]) == 0.0


def test_compute_metrics_empty_and_sample() -> None:
    empty = compute_metrics([0.01] * 5)
    assert empty['sharpe'] is None
    sample = [0.01, -0.005, 0.008, 0.002, -0.012] * 8
    out = compute_metrics(sample)
    assert out['days'] == 40
    assert out['sharpe'] is not None
    assert out['maxDrawdown'] is not None
    assert out['var95'] is not None
    assert out['cvar95'] <= out['var95'] + 1e-9
    assert out['totalReturn'] is not None
