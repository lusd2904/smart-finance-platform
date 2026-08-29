"""8 族因子回测：做多模拟与信号长度。"""

import os
import sys
from datetime import date, timedelta

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_trade.service.backtest_engine import LOOKBACK, factor_signals, simulate_long_only


def _bars(n: int, start: float = 100.0, step: float = 0.0) -> list[dict]:
    origin = date(2024, 1, 2)
    out = []
    price = start
    for i in range(n):
        out.append(
            {
                'date': (origin + timedelta(days=i)).isoformat(),
                'open': price,
                'high': price * 1.01,
                'low': price * 0.99,
                'close': price,
                'volume': 1_000_000,
            }
        )
        price += step
    return out


def test_simulate_long_only_round_trip_profit() -> None:
    klines = _bars(5, start=100.0)
    klines[2]['close'] = 110.0
    klines[3]['close'] = 120.0
    klines[4]['close'] = 120.0
    sim = simulate_long_only(
        klines,
        ['HOLD', 'BUY', 'HOLD', 'SELL', 'HOLD'],
        initial_capital=10000.0,
        fee_rate=0.0,
        slippage=0.0,
    )
    assert sim['trades'] == 2
    assert sim['roundTrips'] == 1
    assert sim['returnPct'] > 0
    assert sim['winRate'] == 100.0
    assert len(sim['equity']) == 5


def test_simulate_hold_never_trades() -> None:
    klines = _bars(8, start=50.0, step=1.0)
    sim = simulate_long_only(klines, ['HOLD'] * 8, initial_capital=1000.0)
    assert sim['trades'] == 0
    assert sim['returnPct'] == 0.0
    assert sim['finalEquity'] == 1000.0


def test_factor_signals_hold_until_lookback(monkeypatch) -> None:
    from module_quant.service.factor_service import FactorService

    klines = _bars(LOOKBACK + 8, start=100.0, step=0.5)

    def fake_compute(cls, bars, profile='balanced', weights=None):
        del cls, bars, profile, weights
        return {
            'ok': True,
            'score': {
                'total': 80,
                'trendDirection': 'up',
                'riskLevel': 'low',
                'tags': ['站上20日线'],
            },
        }

    monkeypatch.setattr(FactorService, 'compute_from_klines', classmethod(fake_compute))
    signals = factor_signals(klines, profile='balanced')
    assert len(signals) == len(klines)
    assert all(s == 'HOLD' for s in signals[:LOOKBACK])
    assert any(s == 'BUY' for s in signals[LOOKBACK:])


def test_factor_signals_sell_on_down_score(monkeypatch) -> None:
    from module_quant.service.factor_service import FactorService

    klines = _bars(LOOKBACK + 5, start=80.0, step=-0.4)

    def fake_compute(cls, bars, profile='balanced', weights=None):
        del cls, bars, profile, weights
        return {
            'ok': True,
            'score': {
                'total': 20,
                'trendDirection': 'down',
                'riskLevel': 'high',
                'tags': [],
            },
        }

    monkeypatch.setattr(FactorService, 'compute_from_klines', classmethod(fake_compute))
    signals = factor_signals(klines, profile='conservative')
    assert all(s == 'HOLD' for s in signals[:LOOKBACK])
    assert all(s == 'SELL' for s in signals[LOOKBACK:])
