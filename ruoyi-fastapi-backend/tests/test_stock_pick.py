import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.stock_pick_scoring import (
    combine_pick_score,
    is_index_symbol,
    merge_candidates,
    normalize_sentiment,
    reco_from_signal,
    select_top_picks,
)
from module_market.service.sync_service import eod_session_date, should_skip_eod


def test_closed_market_drops_index_from_score() -> None:
    closed = combine_pick_score(80, sentiment_raw=2, heat_score=90, index_open=False, index_change_pct=3)
    opened = combine_pick_score(80, sentiment_raw=2, heat_score=90, index_open=True, index_change_pct=3)
    assert closed != opened
    only_factor_sent = combine_pick_score(80, sentiment_raw=2, heat_score=10, index_open=False, index_change_pct=-8)
    assert closed == only_factor_sent


def test_normalize_and_reco() -> None:
    assert normalize_sentiment(0) == 50
    assert normalize_sentiment(10) == 100
    assert reco_from_signal('BUY', 70) == ('买入', '偏多')
    assert reco_from_signal('SELL', 40) == ('回避', '偏空')
    assert is_index_symbol('^GSPC', 'index') is True
    assert is_index_symbol('AAPL', 'mag7') is False


def test_merge_and_select() -> None:
    top = [{'symbol': 'AAPL', 'name': '苹果', 'market': 'US'}]
    feat = [
        {'symbol': 'AAPL', 'name': '苹果', 'market': 'US', 'category': 'mag7'},
        {'symbol': '^DJI', 'name': '道指', 'market': 'US', 'category': 'index'},
        {'symbol': '600519', 'name': '茅台', 'market': 'CN', 'category': 'star'},
    ]
    merged = merge_candidates(top, feat, cap=10)
    assert [r['symbol'] for r in merged] == ['AAPL', '600519']
    rows = [
        {'symbol': 'A', 'market': 'US', 'signal': 'HOLD', 'pickScore': 90},
        {'symbol': 'B', 'market': 'US', 'signal': 'BUY', 'pickScore': 60},
        {'symbol': 'C', 'market': 'CN', 'signal': 'BUY', 'pickScore': 70},
    ]
    picked = select_top_picks(rows, per_market=1)
    us = [r for r in picked if r['market'] == 'US']
    assert us[0]['symbol'] == 'B'


def test_eod_skip_and_session_date() -> None:
    assert should_skip_eod(None, date(2026, 8, 21)) is False
    assert should_skip_eod('2026-08-21', date(2026, 8, 21)) is True
    assert should_skip_eod('2026-08-20', date(2026, 8, 21)) is False
    cn_close = datetime(2026, 8, 21, 15, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert eod_session_date('CN', cn_close) == date(2026, 8, 21)
    us_after = datetime(2026, 8, 19, 5, 30, tzinfo=ZoneInfo('Asia/Shanghai'))
    assert eod_session_date('US', us_after) == date(2026, 8, 18)
