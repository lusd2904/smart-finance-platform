import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.factor_qc_service import (
    ENGINE_VERSION,
    evaluate_factor,
    factor_specs,
    klines_to_panels,
)


def _trending_panel(n_dates: int = 80, n_symbols: int = 20) -> pd.DataFrame:
    """高编号标的趋势更强，20 日动量应对前瞻收益呈正相关。"""
    dates = pd.bdate_range('2023-01-02', periods=n_dates)
    data = {}
    for i in range(n_symbols):
        drift = 0.001 + i * 0.0008
        prices = [100.0]
        for t in range(1, n_dates):
            noise = ((t * (i + 3)) % 7 - 3) * 0.0005
            prices.append(prices[-1] * (1 + drift + noise))
        data[f'S{i:02d}'] = prices
    return pd.DataFrame(data, index=dates)


def test_klines_to_panels_aligns_dates() -> None:
    klines = {
        'AAA': [
            {'date': '2024-01-02', 'close': 10, 'volume': 100},
            {'date': '2024-01-03', 'close': 11, 'volume': 110},
        ],
        'BBB': [
            {'date': '2024-01-03', 'close': 20, 'volume': 200},
            {'date': '2024-01-04', 'close': 21, 'volume': 210},
        ],
    }
    close, volume = klines_to_panels(klines)
    assert list(close.columns) == ['AAA', 'BBB']
    assert close.loc['2024-01-03', 'AAA'] == 11
    assert pd.isna(close.loc['2024-01-02', 'BBB'])
    assert volume.loc['2024-01-03', 'BBB'] == 200


def test_momentum_ic_positive_on_trending_panel() -> None:
    close = _trending_panel()
    mom20 = close.pct_change(20)
    rows = evaluate_factor(mom20, close, periods=(1, 5))
    by_h = {r['horizon']: r for r in rows}
    assert by_h[1]['sampleDates'] >= 20
    assert by_h[1]['icMean'] is not None and by_h[1]['icMean'] > 0.3
    assert by_h[1]['ir'] is not None and by_h[1]['ir'] > 0
    assert by_h[1]['quantiles']
    assert by_h[1]['spread'] is not None and by_h[1]['spread'] > 0


def test_load_close_volume_uses_batch_query(monkeypatch) -> None:
    from module_quant.service import factor_qc_service as qc

    captured: dict = {}

    def fake_many(market, symbols, start='-1y', limit=320):
        captured['market'] = market
        captured['symbols'] = list(symbols)
        captured['start'] = start
        captured['limit'] = limit
        return {
            'AAPL': [{'date': '2024-01-02', 'close': 10, 'volume': 1}],
            'MSFT': [{'date': '2024-01-02', 'close': 20, 'volume': 2}],
        }

    monkeypatch.setattr(qc.InfluxUtil, 'query_klines_many', fake_many)
    monkeypatch.setattr(qc.FactorQcService, 'universe', classmethod(lambda cls, market='US': [('AAPL', 'US'), ('MSFT', 'US')]))
    close, volume = qc.FactorQcService.load_close_volume('US', start='-400d', limit=260)
    assert captured['market'] == 'US'
    assert captured['symbols'] == ['AAPL', 'MSFT']
    assert captured['limit'] == 260
    assert list(close.columns) == ['AAPL', 'MSFT']
    assert volume.loc['2024-01-02', 'MSFT'] == 2


def test_factor_specs_cover_core_families() -> None:
    keys = {s['key'] for s in factor_specs()}
    assert {'mom20', 'reversal5', 'rsi14', 'ma_spread', 'vol_ratio20', 'cs_mom20', 'cs_vol_ratio'} <= keys
    assert ENGINE_VERSION.startswith('alphalens')
