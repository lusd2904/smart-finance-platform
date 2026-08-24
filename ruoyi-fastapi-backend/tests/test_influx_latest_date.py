import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.influx_util import InfluxUtil


def _table(*dates):
    """构造带记录的伪查询结果，record.get_time() 返回对应日期。"""
    table = MagicMock()
    records = []
    for d in dates:
        record = MagicMock()
        record.get_time.return_value = datetime(2026, *d, tzinfo=timezone.utc)
        records.append(record)
    table.records = records
    return [table]


def _query_api(side_effect):
    query_api = MagicMock()
    query_api.query.side_effect = side_effect
    client = MagicMock()
    client.query_api.return_value = query_api
    return client


def test_latest_date_short_window_hit_stops():
    """-7d 窗口命中即返回，不再放宽查询。"""
    calls = []

    def side_effect(flux):
        calls.append(flux)
        assert "range(start: -7d)" in flux
        return _table((8, 21))

    with patch('utils.influx_util.get_client', return_value=_query_api(side_effect)):
        result = InfluxUtil.latest_date('CN', '600000.SH')

    assert result == '2026-08-21'
    assert len(calls) == 1


def test_latest_date_widens_until_hit():
    """短窗全空时逐级放宽（-90d/-2y），首个非空即停。"""

    def side_effect(flux):
        if 'range(start: -7d)' in flux or 'range(start: -90d)' in flux:
            return []
        assert 'range(start: -2y)' in flux
        return _table((4, 10))

    with patch('utils.influx_util.get_client', return_value=_query_api(side_effect)):
        result = InfluxUtil.latest_date('US', 'AAPL')

    assert result == '2026-04-10'


def test_latest_date_all_empty_returns_none():
    """全部窗口（-7d/-90d/-2y/-10y）均无数据时返回 None。"""
    calls = []

    def side_effect(flux):
        calls.append(flux)
        return []

    with patch('utils.influx_util.get_client', return_value=_query_api(side_effect)):
        result = InfluxUtil.latest_date('CN', '000001.SZ')

    assert result is None
    # 四个窗口依次查过一遍
    windows = ('-7d', '-90d', '-2y', '-10y')
    assert len(calls) == 4
    for window, flux in zip(windows, calls, strict=True):
        assert f'range(start: {window})' in flux


def test_latest_date_invalid_symbol_short_circuits():
    """非法 symbol 直接返回 None，不发任何查询。"""
    with patch('utils.influx_util.get_client') as mock_client:
        result = InfluxUtil.latest_date('CN', 'bad; symbol')

    assert result is None
    mock_client.assert_not_called()
