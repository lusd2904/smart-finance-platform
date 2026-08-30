import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.alpha_engine import (
    ALPHA_ENGINE_VERSION,
    attach_cross_section_alphas,
    compute_advanced_factors,
    compute_alpha101,
    compute_alpha158,
)
from module_quant.service import alpha_engine as ae
from module_quant.service.factor_service import (
    compute_alpha_factors,
    compute_family_frame,
    compute_metrics,
    metrics_from_frame_row,
    score_metrics,
)
from module_quant.service.strategy_service import StrategyService


def _synthetic_klines(n: int = 80) -> pd.DataFrame:
    rows = []
    price = 100.0
    for i in range(n):
        price += 0.8 if i % 4 else -0.35
        rows.append(
            {
                'date': f'2024-01-{(i % 28) + 1:02d}',
                'open': price - 0.4,
                'high': price + 0.7,
                'low': price - 0.8,
                'close': price,
                'volume': 1_200_000 + i * 1500,
            }
        )
    return pd.DataFrame(rows)


def test_alpha101_covers_core_formulas() -> None:
    alphas = compute_alpha101(_synthetic_klines())
    for key in ('alpha001', 'alpha006', 'alpha012', 'alpha041', 'alpha054', 'alpha101'):
        assert key in alphas
    assert len(alphas) >= 40
    assert all(isinstance(v, float) for v in alphas.values())


def test_alpha158_has_kbar_and_rolling_windows() -> None:
    feats = compute_alpha158(_synthetic_klines())
    for key in ('KMID', 'KLEN', 'OPEN0', 'VOLUME0', 'ROC5', 'MA20', 'STD20', 'CORR20', 'RSV20', 'SUMD20'):
        assert key in feats
    assert len(feats) >= 140
    assert all(isinstance(v, float) for v in feats.values())


def test_advanced_bundle_keeps_legacy_keys() -> None:
    bundle = compute_advanced_factors(_synthetic_klines())
    assert bundle['version'] == ALPHA_ENGINE_VERSION
    assert bundle['alpha101Count'] >= 40
    assert bundle['alpha158Count'] >= 140
    assert 'alpha006' in bundle
    assert 'qlib_sharpe20' in bundle
    flat = compute_alpha_factors(_synthetic_klines())
    assert flat['alpha101Count'] == bundle['alpha101Count']


def test_attach_cross_section_alphas_ranks_universe() -> None:
    rows = [
        {
            'symbol': 'AAA',
            'return20': 0.10,
            'rsi14': 70,
            'volumeRatio20': 1.8,
            'distanceHigh20': -0.01,
            'alpha101': {
                'alpha001': 0.9,
                'alpha006': -0.2,
                'alpha012': 0.3,
                'alpha023': 0.1,
                'alpha041': 0.4,
                'alpha101': 0.8,
            },
        },
        {
            'symbol': 'BBB',
            'return20': 0.02,
            'rsi14': 50,
            'volumeRatio20': 1.0,
            'distanceHigh20': -0.05,
            'alpha101': {
                'alpha001': 0.2,
                'alpha006': 0.1,
                'alpha012': 0.0,
                'alpha023': 0.2,
                'alpha041': 0.1,
                'alpha101': 0.2,
            },
        },
        {
            'symbol': 'CCC',
            'return20': -0.08,
            'rsi14': 30,
            'volumeRatio20': 0.6,
            'distanceHigh20': -0.12,
            'alpha101': {
                'alpha001': -0.4,
                'alpha006': 0.5,
                'alpha012': -0.2,
                'alpha023': -0.1,
                'alpha041': -0.3,
                'alpha101': -0.1,
            },
        },
    ]
    attach_cross_section_alphas(rows)
    by_sym = {r['symbol']: r['alphaCs'] for r in rows}
    assert by_sym['AAA']['csMom20'] == 1.0
    assert by_sym['CCC']['csMom20'] < by_sym['BBB']['csMom20']
    assert 'csAlpha001' in by_sym['AAA']
    assert 'csAlpha101' in by_sym['AAA']
    assert rows[0]['alphaCsCount'] >= 8


def test_compute_metrics_attaches_alpha_counts() -> None:
    metrics = compute_metrics(_synthetic_klines().to_dict('records'))
    assert metrics['ok'] is True
    assert metrics['alpha101Count'] >= 40
    assert metrics['alpha158Count'] >= 140
    assert 'alpha101' in metrics['alphaFactors']


def test_compute_metrics_can_skip_alpha() -> None:
    metrics = compute_metrics(_synthetic_klines().to_dict('records'), include_alpha=False)
    assert metrics['ok'] is True
    assert metrics['alpha101Count'] == 0
    assert metrics['alphaFactors']['alpha101'] == {}


def test_family_last_only_matches_full_last_row() -> None:
    klines = _synthetic_klines(320).to_dict('records')
    full = compute_family_frame(klines)
    last = compute_family_frame(klines, last_only=True)
    assert full is not None and last is not None
    assert len(last) == 1
    a = metrics_from_frame_row(full.iloc[-1], 320)
    b = metrics_from_frame_row(last.iloc[-1], 320)
    assert a == b
    assert score_metrics(a)['total'] == score_metrics(b)['total']


def test_alpha158_last_window_matches_rolling_last() -> None:
    df = _synthetic_klines(320)
    feats = compute_alpha158(df)
    frame = ae._prep(df)
    assert frame is not None
    c = frame['close']
    h = frame['high']
    low = frame['low']
    last_c = float(c.iloc[-1])
    last_o = float(frame['open'].iloc[-1])
    n = len(c)
    assert feats['KMID'] == round(ae._finite((last_c - last_o) / (last_o + 1e-12)), 6)
    assert feats['MA20'] == round(ae._finite(ae._ts_mean(c, 20).iloc[-1] / (last_c + 1e-12)), 6)
    assert feats['STD20'] == round(ae._finite(ae._ts_std(c, 20).iloc[-1] / (last_c + 1e-12)), 6)
    assert feats['RANK20'] == round(ae._finite(ae._ts_rank(c, 20).iloc[-1]), 6)
    assert feats['CORR20'] == round(ae._finite(ae._ts_corr(c, np.log(frame['volume'] + 1.0), 20).iloc[-1]), 6)
    slope = ae._slope(c, 20)
    mean = ae._ts_mean(c, 20)
    resid = last_c - (float(slope.iloc[-1]) * (n - 1) + float(mean.iloc[-1]))
    assert feats['RESI20'] == round(ae._finite(resid / (last_c + 1e-12)), 6)
    assert feats['IMAX20'] == round(ae._finite(ae._ts_argmax(h, 20).iloc[-1] / 20.0), 6)
    assert feats['MIN60'] == round(ae._finite(ae._ts_min(low, 60).iloc[-1] / (last_c + 1e-12)), 6)


def test_evaluate_symbol_skips_alpha() -> None:
    klines = _synthetic_klines(80).to_dict('records')
    seen: dict[str, bool] = {}

    def fake_from_klines(*_args, **kwargs):
        seen['include_alpha'] = kwargs.get('include_alpha', True)
        return {
            'ok': True,
            'score': {'total': 70, 'riskLevel': 'low', 'trendDirection': 'up', 'tags': ['强势']},
            'metrics': {'latestClose': 10.0},
        }

    from unittest.mock import patch

    with patch('module_quant.service.strategy_service.FactorService.compute_from_klines', fake_from_klines):
        result = StrategyService.evaluate_symbol('AAPL', 'US', klines=klines)
    assert result['ok'] is True
    assert seen['include_alpha'] is False
