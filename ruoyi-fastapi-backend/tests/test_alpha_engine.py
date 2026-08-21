import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.alpha_engine import (
    ALPHA_ENGINE_VERSION,
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


def test_compute_metrics_attaches_alpha_counts() -> None:
    metrics = compute_metrics(_synthetic_klines().to_dict('records'))
    assert metrics['ok'] is True
    assert metrics['alpha101Count'] >= 40
    assert metrics['alpha158Count'] >= 140
    assert 'alpha101' in metrics['alphaFactors']
