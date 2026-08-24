import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.time_format_util import apply_beijing_times, format_beijing_datetime


def test_aware_utc_converts_to_beijing() -> None:
    utc = datetime(2026, 8, 24, 4, 55, 0, tzinfo=timezone.utc)
    assert format_beijing_datetime(utc) == '2026-08-24 12:55:00'


def test_naive_keeps_wall_clock() -> None:
    naive = datetime(2026, 8, 24, 20, 0, 0)
    assert format_beijing_datetime(naive) == '2026-08-24 20:00:00'


def test_iso_z_string_converts_to_beijing() -> None:
    assert format_beijing_datetime('2026-08-24T04:55:00Z') == '2026-08-24 12:55:00'
    assert format_beijing_datetime('2026-08-24T04:55:00+00:00') == '2026-08-24 12:55:00'


def test_iso_naive_string_no_shift() -> None:
    assert format_beijing_datetime('2026-08-24T20:00:00') == '2026-08-24 20:00:00'


def test_apply_beijing_times_on_payload() -> None:
    payload = {
        'createTime': datetime(2026, 8, 24, 4, 55, 0, tzinfo=timezone.utc),
        'title': 'hello',
        'nested': {'pubTime': '2026-08-24T04:55:00Z'},
    }
    out = apply_beijing_times(payload)
    assert out['createTime'] == '2026-08-24 12:55:00'
    assert out['title'] == 'hello'
    assert out['nested']['pubTime'] == '2026-08-24 12:55:00'
    assert 'Z' not in out['createTime']
    assert 'T' not in out['createTime']
