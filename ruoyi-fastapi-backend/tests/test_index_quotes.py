import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pathlib import Path

from module_market.service.index_session import (
    is_in_session,
    is_live_kline_session,
    kline_session_tag,
    should_include_market,
    us_session_tag,
)


def test_index_specs_three_per_market() -> None:
    text = (Path(__file__).resolve().parents[1] / 'module_market/service/index_quotes_service.py').read_text(
        encoding='utf-8'
    )
    for code in ('usDJI', 'r_hkHSCEI', 'sz399006', 'sh000688'):
        assert f"'code': '{code}'" in text
    assert text.index("'usINX'") < text.index("'usDJI'")
    assert "CACHE_KEY = 'market:index:quotes:v3'" in text


def test_us_always_included_even_when_closed() -> None:
    sunday = datetime(2026, 8, 23, 12, 0, tzinfo=ZoneInfo('America/New_York'))
    overnight = datetime(2026, 8, 25, 1, 0, tzinfo=ZoneInfo('America/New_York'))
    regular = datetime(2026, 8, 25, 10, 0, tzinfo=ZoneInfo('America/New_York'))
    assert should_include_market('US', sunday) is True
    assert should_include_market('US', overnight) is True
    assert should_include_market('US', regular) is True
    assert is_in_session('US', sunday) is False
    assert is_in_session('US', overnight) is False
    assert is_in_session('US', regular) is True


def test_hk_only_during_local_session() -> None:
    tz = ZoneInfo('Asia/Hong_Kong')
    morning = datetime(2026, 8, 25, 10, 0, tzinfo=tz)
    lunch = datetime(2026, 8, 25, 12, 30, tzinfo=tz)
    afternoon = datetime(2026, 8, 25, 14, 0, tzinfo=tz)
    closed = datetime(2026, 8, 25, 16, 30, tzinfo=tz)
    weekend = datetime(2026, 8, 23, 10, 0, tzinfo=tz)
    assert should_include_market('HK', morning) is True
    assert should_include_market('HK', lunch) is False
    assert should_include_market('HK', afternoon) is True
    assert should_include_market('HK', closed) is False
    assert should_include_market('HK', weekend) is False


def test_cn_only_during_local_session() -> None:
    tz = ZoneInfo('Asia/Shanghai')
    morning = datetime(2026, 8, 25, 10, 0, tzinfo=tz)
    lunch = datetime(2026, 8, 25, 12, 0, tzinfo=tz)
    afternoon = datetime(2026, 8, 25, 14, 0, tzinfo=tz)
    after_close = datetime(2026, 8, 25, 15, 30, tzinfo=tz)
    assert should_include_market('CN', morning) is True
    assert should_include_market('CN', lunch) is False
    assert should_include_market('CN', afternoon) is True
    assert should_include_market('CN', after_close) is False
    # 15:20 港股仍开、A 股已收
    hk_still_open = datetime(2026, 8, 25, 15, 20, tzinfo=ZoneInfo('Asia/Hong_Kong'))
    assert should_include_market('HK', hk_still_open) is True
    assert should_include_market('CN', datetime(2026, 8, 25, 15, 20, tzinfo=tz)) is False


def test_us_session_tag_windows() -> None:
    et = ZoneInfo('America/New_York')
    assert us_session_tag(datetime(2026, 8, 23, 12, 0, tzinfo=et)) == 'closed'  # Sunday
    assert us_session_tag(datetime(2026, 8, 29, 10, 0, tzinfo=et)) == 'closed'  # Saturday
    assert us_session_tag(datetime(2026, 8, 25, 1, 0, tzinfo=et)) == 'overnight'
    assert us_session_tag(datetime(2026, 8, 25, 4, 0, tzinfo=et)) == 'pre'
    assert us_session_tag(datetime(2026, 8, 25, 9, 29, tzinfo=et)) == 'pre'
    assert us_session_tag(datetime(2026, 8, 25, 9, 30, tzinfo=et)) == 'regular'
    assert us_session_tag(datetime(2026, 8, 25, 16, 0, tzinfo=et)) == 'post'
    assert us_session_tag(datetime(2026, 8, 25, 19, 59, tzinfo=et)) == 'post'
    assert us_session_tag(datetime(2026, 8, 25, 20, 0, tzinfo=et)) == 'overnight'
    assert us_session_tag(datetime(2026, 8, 28, 21, 0, tzinfo=et)) == 'overnight'  # Friday night


def test_is_live_kline_session_us_extended_hk_cn_regular() -> None:
    et = ZoneInfo('America/New_York')
    hk = ZoneInfo('Asia/Hong_Kong')
    cn = ZoneInfo('Asia/Shanghai')
    overnight = datetime(2026, 8, 25, 1, 0, tzinfo=et)
    sunday = datetime(2026, 8, 23, 12, 0, tzinfo=et)
    assert is_live_kline_session('US', overnight) is True
    assert is_in_session('US', overnight) is False
    assert is_live_kline_session('US', sunday) is False
    assert should_include_market('US', sunday) is True
    assert kline_session_tag('US', overnight) == 'overnight'
    assert is_live_kline_session('HK', datetime(2026, 8, 25, 10, 0, tzinfo=hk)) is True
    assert is_live_kline_session('HK', datetime(2026, 8, 25, 12, 30, tzinfo=hk)) is False
    assert is_live_kline_session('HK', datetime(2026, 8, 23, 10, 0, tzinfo=hk)) is False
    assert kline_session_tag('HK', datetime(2026, 8, 25, 16, 30, tzinfo=hk)) == 'closed'
    assert is_live_kline_session('CN', datetime(2026, 8, 25, 10, 0, tzinfo=cn)) is True
    assert is_live_kline_session('CN', datetime(2026, 8, 25, 15, 30, tzinfo=cn)) is False
    assert kline_session_tag('CN', datetime(2026, 8, 25, 10, 0, tzinfo=cn)) == 'regular'
