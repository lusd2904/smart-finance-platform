from datetime import datetime

from module_market.service.heat_eod import _merge_candidates, _top50_snapshot_row


def test_merge_candidates_keeps_last() -> None:
    merged = _merge_candidates(
        [{'symbol': 'AAPL', 'name': 'Apple', 'turnover': 1, 'last': None}],
        [{'symbol': 'AAPL', 'name': 'Apple', 'turnover': 2, 'last': 190.5}],
    )
    assert merged[0]['last'] == 190.5
    assert merged[0]['turnover'] == 2


def test_top50_snapshot_row_persists_last() -> None:
    as_of = datetime(2026, 9, 5, 16, 0, 0)
    row = _top50_snapshot_row(
        'US',
        '2026-09-04',
        {
            'rankNo': 1,
            'symbol': 'AAPL',
            'name': 'Apple',
            'market_cap': 3e12,
            'turnover': 2e9,
            'change_pct': 1.2,
            'last': 190.5,
            'currency': 'USD',
        },
        as_of,
    )
    assert row['last'] == 190.5
    assert row['symbol'] == 'AAPL'
    zero = _top50_snapshot_row(
        'US',
        '2026-09-04',
        {
            'rankNo': 2,
            'symbol': 'AMD',
            'name': 'AMD',
            'market_cap': 1,
            'turnover': 1,
            'change_pct': 0.8,
            'last': 0,
            'currency': 'USD',
        },
        as_of,
    )
    assert zero['last'] is None
