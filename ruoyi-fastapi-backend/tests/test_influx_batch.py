"""批量 Influx 查询：分片、单片失败不丢整批、走 batch client。"""

import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils import influx_util
from utils.influx_util import InfluxQueryError, InfluxUtil, kline_chunk_size


class _Rec:
    def __init__(self, symbol: str, day: str = '2024-01-02') -> None:
        self.values = {
            'symbol': symbol,
            'open': 1,
            'high': 2,
            'low': 0.5,
            'close': 1.5,
            'volume': 100,
        }
        self._t = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)

    def get_time(self):
        return self._t


def _tables_for(symbols: list[str]):
    return [SimpleNamespace(records=[_Rec(s) for s in symbols])]


def test_kline_chunk_size_clamped(monkeypatch) -> None:
    monkeypatch.setattr(influx_util.InfluxConfig, 'influx_kline_chunk', 10, raising=False)
    assert kline_chunk_size() == 10
    monkeypatch.setattr(influx_util.InfluxConfig, 'influx_kline_chunk', 0, raising=False)
    assert kline_chunk_size() == 1
    monkeypatch.setattr(influx_util.InfluxConfig, 'influx_kline_chunk', 99, raising=False)
    assert kline_chunk_size() == 40


def test_query_klines_many_keeps_good_chunks_when_one_fails(monkeypatch) -> None:
    monkeypatch.setattr(influx_util, 'kline_chunk_size', lambda: 1)
    calls: list[str] = []

    class _Api:
        def query(self, flux: str):
            if '"AAPL"' in flux:
                calls.append('AAPL-fail')
                raise TimeoutError('read timed out')
            if '"MSFT"' in flux:
                calls.append('MSFT')
                return _tables_for(['MSFT'])
            calls.append('other')
            return []

    class _Client:
        def query_api(self):
            return _Api()

    monkeypatch.setattr(influx_util, 'get_batch_client', lambda: _Client())
    out = InfluxUtil.query_klines_many('US', ['AAPL', 'MSFT'], start='-400d', limit=10)
    assert 'MSFT' in out
    assert 'AAPL' not in out
    assert out['MSFT'][0]['close'] == 1.5
    assert calls.count('AAPL-fail') == 2  # 重试一次


def test_query_klines_many_uses_equality_not_contains(monkeypatch) -> None:
    seen: list[str] = []

    class _Api:
        def query(self, flux: str):
            seen.append(flux)
            return []

    class _Client:
        def query_api(self):
            return _Api()

    monkeypatch.setattr(influx_util, 'kline_chunk_size', lambda: 10)
    monkeypatch.setattr(influx_util, 'get_batch_client', lambda: _Client())
    InfluxUtil.query_klines_many('US', ['AAPL', 'MSFT'], start='-10d', limit=5)
    assert seen
    assert 'contains(' not in seen[0]
    assert 'r.symbol == "AAPL"' in seen[0]
    assert 'r.symbol == "MSFT"' in seen[0]
    assert 'stop: now()' in seen[0]


def test_query_klines_many_all_fail_raises(monkeypatch) -> None:
    monkeypatch.setattr(influx_util, 'kline_chunk_size', lambda: 10)

    class _Api:
        def query(self, flux: str):
            raise TimeoutError('read timed out')

    class _Client:
        def query_api(self):
            return _Api()

    monkeypatch.setattr(influx_util, 'get_batch_client', lambda: _Client())
    try:
        InfluxUtil.query_klines_many('US', ['AAPL'], start='-10d', limit=5)
        raise AssertionError('expected InfluxQueryError')
    except InfluxQueryError:
        pass


def test_batch_timeout_not_shorter_than_short(monkeypatch) -> None:
    monkeypatch.setattr(influx_util.InfluxConfig, 'influx_timeout_ms', 8000, raising=False)
    monkeypatch.setattr(influx_util.InfluxConfig, 'influx_batch_timeout_ms', 1000, raising=False)
    assert influx_util._batch_timeout_ms() >= influx_util._short_timeout_ms()
