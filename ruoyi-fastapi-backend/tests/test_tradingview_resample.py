import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.tradingview_service import _normalize_resolution, _resample_klines


def test_normalize_resolution() -> None:
    assert _normalize_resolution('1D') == 'D'
    assert _normalize_resolution('W') == 'W'
    assert _normalize_resolution('15') == '15'


def test_weekly_resample_reduces_bars() -> None:
    klines = []
    for day in range(1, 15):
        klines.append(
            {
                'date': f'2024-01-{day:02d}',
                'open': 10 + day,
                'high': 11 + day,
                'low': 9 + day,
                'close': 10.5 + day,
                'volume': 1000,
            }
        )
    weekly = _resample_klines(klines, 'W')
    assert 0 < len(weekly) < len(klines)
    daily = _resample_klines(klines, 'D')
    assert len(daily) == len(klines)
