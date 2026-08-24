import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.constant.instruments import (
    LISTED_CATEGORY,
    UNIVERSE_PAGE_SIZE_DEFAULT,
    UNIVERSE_PAGE_SIZE_MAX,
    build_quotes_from_ranked_bars,
    clamp_universe_page,
    featured_list_excludes_listed,
    sanitize_instrument_keyword,
)


def test_featured_list_still_excludes_listed_without_keyword() -> None:
    assert featured_list_excludes_listed(None, None) is True
    assert featured_list_excludes_listed('', '') is True
    assert featured_list_excludes_listed('listed', None) is False
    assert featured_list_excludes_listed(None, 'AAPL') is False
    assert featured_list_excludes_listed(LISTED_CATEGORY, '700') is False


def test_sanitize_keyword_strips_wildcards() -> None:
    assert sanitize_instrument_keyword('  A%APL_ ') == 'AAPL'
    assert sanitize_instrument_keyword(None) == ''
    assert len(sanitize_instrument_keyword('x' * 80)) == 32


def test_clamp_universe_page() -> None:
    assert clamp_universe_page(None, None) == (1, UNIVERSE_PAGE_SIZE_DEFAULT)
    assert clamp_universe_page(0, 0) == (1, UNIVERSE_PAGE_SIZE_DEFAULT)
    assert clamp_universe_page(-3, 9999) == (1, UNIVERSE_PAGE_SIZE_MAX)
    assert clamp_universe_page(2, 80) == (2, 80)
    assert clamp_universe_page('3', '20') == (3, 20)
    assert clamp_universe_page('x', 'y') == (1, UNIVERSE_PAGE_SIZE_DEFAULT)


def test_build_quotes_from_ranked_bars() -> None:
    rows = [
        SimpleNamespace(symbol='AAPL', rn=1, close_price=110.0, trade_date='2026-08-21', volume=100),
        SimpleNamespace(symbol='AAPL', rn=2, close_price=100.0, trade_date='2026-08-20', volume=90),
        SimpleNamespace(symbol='0700.HK', rn=1, close_price=320.0, trade_date='2026-08-21', volume=1),
        SimpleNamespace(symbol='0700.HK', rn=2, close_price=None, trade_date='2026-08-20', volume=1),
        SimpleNamespace(symbol='', rn=1, close_price=1, trade_date='2026-08-21', volume=1),
    ]
    quotes = build_quotes_from_ranked_bars(rows)
    assert quotes['AAPL']['price'] == 110.0
    assert quotes['AAPL']['prevClose'] == 100.0
    assert quotes['AAPL']['changeRate'] == 10.0
    assert quotes['AAPL']['up'] is True
    assert quotes['AAPL']['tradeDate'] == '2026-08-21'
    assert quotes['0700.HK']['price'] == 320.0
    assert quotes['0700.HK']['changeRate'] is None
    assert quotes['0700.HK']['up'] is None
    assert '' not in quotes
