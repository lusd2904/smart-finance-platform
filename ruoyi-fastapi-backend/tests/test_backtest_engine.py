"""8 族因子回测：做多模拟与信号长度。"""

import os
import sys
import time
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
    buy = {'total': 80, 'trendDirection': 'up', 'riskLevel': 'low', 'tags': ['站上20日线']}

    def fake_series(cls, bars, profile='balanced', weights=None):
        del cls, profile, weights
        return [None] * LOOKBACK + [buy] * (len(bars) - LOOKBACK)

    monkeypatch.setattr(FactorService, 'compute_score_series', classmethod(fake_series))
    signals = factor_signals(klines, profile='balanced')
    assert len(signals) == len(klines)
    assert all(s == 'HOLD' for s in signals[:LOOKBACK])
    assert any(s == 'BUY' for s in signals[LOOKBACK:])


def test_factor_signals_sell_on_down_score(monkeypatch) -> None:
    from module_quant.service.factor_service import FactorService

    klines = _bars(LOOKBACK + 5, start=80.0, step=-0.4)
    sell = {'total': 20, 'trendDirection': 'down', 'riskLevel': 'high', 'tags': []}

    def fake_series(cls, bars, profile='conservative', weights=None):
        del cls, profile, weights
        return [None] * LOOKBACK + [sell] * (len(bars) - LOOKBACK)

    monkeypatch.setattr(FactorService, 'compute_score_series', classmethod(fake_series))
    signals = factor_signals(klines, profile='conservative')
    assert all(s == 'HOLD' for s in signals[:LOOKBACK])
    assert all(s == 'SELL' for s in signals[LOOKBACK:])


def test_score_series_matches_prefix_snapshots() -> None:
    from module_quant.service.factor_service import FactorService

    klines = _bars(80, start=100.0, step=0.35)
    series = FactorService.compute_score_series(klines, 'balanced')
    for idx in (30, 45, 79):
        prefix = FactorService.compute_from_klines(klines[: idx + 1], 'balanced', include_alpha=False)
        assert prefix.get('ok')
        assert series[idx] is not None
        assert series[idx]['total'] == prefix['score']['total']
        assert series[idx]['trendDirection'] == prefix['score']['trendDirection']
        assert series[idx]['riskLevel'] == prefix['score']['riskLevel']


def test_factor_signals_one_pass_stays_under_half_second() -> None:
    klines = _bars(320, start=100.0, step=0.12)
    started = time.perf_counter()
    signals = factor_signals(klines, profile='balanced')
    elapsed = time.perf_counter() - started
    assert len(signals) == 320
    assert elapsed < 0.5
