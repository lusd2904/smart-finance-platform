import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.alpha_engine import (
    ALPHA_ENGINE_VERSION,
    attach_cross_section_alphas,
    compute_advanced_factors,
    compute_alpha101,
    compute_alpha158,
)
from module_quant.service.factor_service import compute_alpha_factors, compute_metrics


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
