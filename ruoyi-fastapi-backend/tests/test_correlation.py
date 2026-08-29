"""自选相关矩阵：对齐收益与 Pearson。"""

import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.correlation_service import aligned_returns, correlation_matrix, pearson


def test_pearson_perfect_and_inverse() -> None:
    xs = [0.01 * i for i in range(30)]
    ys = list(xs)
    zs = [-v for v in xs]
    assert pearson(xs, ys) is not None
    assert abs(pearson(xs, ys) - 1.0) < 1e-9
    assert abs(pearson(xs, zs) + 1.0) < 1e-9
    assert pearson(xs[:5], ys[:5]) is None


def test_aligned_returns_and_matrix() -> None:
    series = {
        'AAA': {f'2026-01-{i:02d}': 10 + i for i in range(1, 40)},
        'BBB': {f'2026-01-{i:02d}': 20 + i * 2 for i in range(1, 40)},
    }
    rets = aligned_returns(series)
    assert set(rets) == {'AAA', 'BBB'}
    assert len(rets['AAA']) >= 20
    matrix = correlation_matrix(rets, ['AAA', 'BBB'])
    assert matrix[0][0] == 1.0
    assert matrix[1][1] == 1.0
    assert matrix[0][1] is not None
    assert matrix[0][1] > 0.9
