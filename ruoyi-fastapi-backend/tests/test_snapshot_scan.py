import asyncio
import os
import sys
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.dao.quant_dao import QuantSnapshotDao
from module_quant.entity.do.quant_do import QuantAlpha101Value, QuantAlpha158Value, QuantFactorSnapshot
from module_quant.service import snapshot_service as ss
from module_quant.service.quant_service import QuantService
from module_quant.service.snapshot_service import SnapshotService


def _ok_factor(close: float = 10.0) -> dict:
    return {
        'ok': True,
        'metrics': {
            'tradeDate': '2024-01-02',
            'latestClose': close,
            'alpha101Count': 1,
            'alpha158Count': 0,
            'alpha101': {'alpha006': 0.1},
            'alpha158': {},
            'return20': 0.05,
            'rsi14': 55,
            'volumeRatio20': 1.2,
            'distanceHigh20': 0.01,
        },
        'score': {'total': 70, 'riskLevel': 'low', 'trendDirection': 'up'},
    }


def _scan_stack(*extra: object) -> ExitStack:
    stack = ExitStack()
    for cm in extra:
        stack.enter_context(cm)
    stack.enter_context(patch.object(QuantService, 'load_profile_config', AsyncMock(return_value={'buy': 64})))
    stack.enter_context(patch.object(ss.QuantSnapshotDao, 'upsert_factor_snapshot', AsyncMock()))
    stack.enter_context(patch.object(ss.QuantSnapshotDao, 'replace_alpha_values', AsyncMock()))
    stack.enter_context(patch.object(ss.QuantSnapshotDao, 'upsert_factor_snapshots_bulk', AsyncMock()))
    stack.enter_context(patch.object(ss.QuantSnapshotDao, 'replace_alpha_values_bulk', AsyncMock()))
    stack.enter_context(patch.object(ss.QuantSnapshotDao, 'add_readmodel_snapshot', AsyncMock()))
    stack.enter_context(patch.object(ss.ReadModelService, 'put_scheduled', AsyncMock()))
    stack.enter_context(patch.object(SnapshotService, 'build_overview_payload', AsyncMock(return_value={'ok': True})))
    return stack


def test_daily_factor_scan_batches_klines_per_market() -> None:
    many_calls: list[tuple] = []

    def fake_many(market, symbols, start='-1y', limit=320):
        many_calls.append((market, list(symbols), start, limit))
        return {
            'AAPL': [{'date': '2024-01-02', 'close': 10, 'volume': 1}],
            'MSFT': [{'date': '2024-01-02', 'close': 20, 'volume': 2}],
        }

    compute_calls: list[list] = []

    def fake_from_klines(klines, strategy_profile='balanced', weights=None):
        compute_calls.append(list(klines))
        close = klines[0]['close'] if klines else 0
        return _ok_factor(close)

    query_klines = MagicMock(side_effect=AssertionError('query_klines'))
    compute_symbol = MagicMock(side_effect=AssertionError('compute_symbol'))

    async def _run() -> dict:
        db = AsyncMock()
        with _scan_stack(
            patch.object(
                SnapshotService,
                '_scan_universe',
                classmethod(lambda cls: [('AAPL', '苹果', 'US'), ('MSFT', '微软', 'US')]),
            ),
            patch.object(ss.InfluxUtil, 'query_klines_many', fake_many),
            patch.object(ss.InfluxUtil, 'query_klines', query_klines),
            patch.object(ss.FactorService, 'compute_from_klines', fake_from_klines),
            patch.object(ss.FactorService, 'compute_symbol', compute_symbol),
        ):
            return await SnapshotService.run_daily_factor_scan(db, profile='balanced')

    payload = asyncio.run(_run())
    assert len(many_calls) == 1
    assert many_calls[0] == ('US', ['AAPL', 'MSFT'], '-1y', 320)
    assert len(compute_calls) == 2
    assert compute_calls[0][0]['close'] == 10
    assert compute_calls[1][0]['close'] == 20
    assert payload['symbolCount'] == 2
    assert payload['failedCount'] == 0
    assert {it['symbol'] for it in payload['items']} == {'AAPL', 'MSFT'}
    query_klines.assert_not_called()
    compute_symbol.assert_not_called()


def test_daily_factor_scan_market_failure_does_not_drop_others() -> None:
    many_calls: list[str] = []

    def fake_many(market, symbols, start='-1y', limit=320):
        many_calls.append(market)
        if market == 'HK':
            raise RuntimeError('hk influx down')
        return {sym: [{'date': '2024-01-02', 'close': 10}] for sym in symbols}

    async def _run() -> dict:
        db = AsyncMock()
        with _scan_stack(
            patch.object(
                SnapshotService,
                '_scan_universe',
                classmethod(
                    lambda cls: [
                        ('AAPL', '苹果', 'US'),
                        ('MSFT', '微软', 'US'),
                        ('0700.HK', '腾讯', 'HK'),
                    ]
                ),
            ),
            patch.object(ss.InfluxUtil, 'query_klines_many', fake_many),
            patch.object(ss.FactorService, 'compute_from_klines', lambda *_a, **_k: _ok_factor()),
            patch.object(ss.FactorService, 'compute_symbol', MagicMock(side_effect=AssertionError('compute_symbol'))),
            patch.object(ss.InfluxUtil, 'query_klines', MagicMock(side_effect=AssertionError('query_klines'))),
        ):
            return await SnapshotService.run_daily_factor_scan(db, profile='balanced')

    payload = asyncio.run(_run())
    assert many_calls == ['US', 'HK']
    assert payload['symbolCount'] == 2
    assert payload['failedCount'] == 1
    assert {it['symbol'] for it in payload['items']} == {'AAPL', 'MSFT'}
    assert payload['failed'][0]['symbol'] == '0700.HK'


def test_daily_factor_scan_persists_with_bulk_dao() -> None:
    async def _run() -> dict:
        db = AsyncMock()
        with _scan_stack(
            patch.object(
                SnapshotService,
                '_scan_universe',
                classmethod(lambda cls: [('AAPL', '苹果', 'US'), ('MSFT', '微软', 'US')]),
            ),
            patch.object(
                ss.InfluxUtil,
                'query_klines_many',
                lambda market, symbols, start='-1y', limit=320: {
                    sym: [{'date': '2024-01-02', 'close': 10}] for sym in symbols
                },
            ),
            patch.object(ss.FactorService, 'compute_from_klines', lambda *_a, **_k: _ok_factor()),
        ):
            payload = await SnapshotService.run_daily_factor_scan(db, profile='balanced')
            ss.QuantSnapshotDao.upsert_factor_snapshots_bulk.assert_awaited_once()
            ss.QuantSnapshotDao.replace_alpha_values_bulk.assert_awaited_once()
            factor_items = ss.QuantSnapshotDao.upsert_factor_snapshots_bulk.await_args.args[1]
            alpha_snaps = ss.QuantSnapshotDao.replace_alpha_values_bulk.await_args.args[1]
            assert len(factor_items) == 2
            assert len(alpha_snaps) == 2
            ss.QuantSnapshotDao.upsert_factor_snapshot.assert_not_awaited()
            ss.QuantSnapshotDao.replace_alpha_values.assert_not_awaited()
            return payload

    payload = asyncio.run(_run())
    assert payload['symbolCount'] == 2


def test_daily_factor_scan_skips_bulk_when_empty() -> None:
    async def _run() -> dict:
        db = AsyncMock()
        with _scan_stack(
            patch.object(SnapshotService, '_scan_universe', classmethod(lambda cls: [])),
            patch.object(ss.InfluxUtil, 'query_klines_many', MagicMock(side_effect=AssertionError('query_klines_many'))),
        ):
            payload = await SnapshotService.run_daily_factor_scan(db, profile='balanced')
            ss.QuantSnapshotDao.upsert_factor_snapshots_bulk.assert_not_awaited()
            ss.QuantSnapshotDao.replace_alpha_values_bulk.assert_not_awaited()
            return payload

    payload = asyncio.run(_run())
    assert payload['symbolCount'] == 0
    assert payload['failedCount'] == 0


class _ScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _ExecuteResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._rows)


def _factor_item(symbol: str, market: str = 'US', total: float = 70) -> dict:
    return {
        'symbol': symbol,
        'market': market,
        'as_of': '2024-01-02',
        'score_total': total,
        'risk_level': 'low',
        'trend_direction': 'up',
        'alpha101_count': 1,
        'alpha158_count': 0,
        'score_json': '{}',
        'alpha_json': '{}',
    }


def test_upsert_factor_snapshots_bulk_selects_once_for_two_items() -> None:
    existing = SimpleNamespace(
        symbol='AAPL',
        market='US',
        as_of=None,
        score_total=None,
        risk_level=None,
        trend_direction=None,
        alpha101_count=0,
        alpha158_count=0,
        score_json=None,
        alpha_json=None,
        create_time=None,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ExecuteResult([existing]))
    db.add_all = MagicMock()
    db.flush = AsyncMock()

    items = [_factor_item('AAPL', total=71), _factor_item('MSFT', total=60)]
    rows = asyncio.run(QuantSnapshotDao.upsert_factor_snapshots_bulk(db, items))

    assert db.execute.await_count == 1
    db.flush.assert_awaited_once()
    db.add_all.assert_called_once()
    added = db.add_all.call_args.args[0]
    assert len(added) == 1
    assert isinstance(added[0], QuantFactorSnapshot)
    assert added[0].symbol == 'MSFT'
    assert existing.score_total == 71
    assert existing.as_of == '2024-01-02'
    assert len(rows) == 2


def test_upsert_factor_snapshots_bulk_skips_empty() -> None:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    assert asyncio.run(QuantSnapshotDao.upsert_factor_snapshots_bulk(db, [])) == []
    db.execute.assert_not_called()
    db.flush.assert_not_called()


def test_replace_alpha_values_bulk_deletes_once_per_model() -> None:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    snaps = [
        {
            'symbol': 'AAPL',
            'market': 'US',
            'asOf': '2024-01-02',
            'alpha101': {
                'alpha006': 0.1,
                'nested': {'x': 1},
                'bad': 'xx',
                'nanv': float('nan'),
            },
            'alpha158': {'SUM60': 1.5},
        },
        {
            'symbol': 'MSFT',
            'market': 'US',
            'asOf': '2024-01-02',
            'alpha101': {'alpha001': 2},
            'alpha158': {},
        },
    ]
    asyncio.run(QuantSnapshotDao.replace_alpha_values_bulk(db, snaps))

    assert db.execute.await_count == 2
    db.add_all.assert_called_once()
    added = db.add_all.call_args.args[0]
    keys = {(type(row).__name__, row.symbol, row.factor_key) for row in added}
    assert keys == {
        (QuantAlpha101Value.__name__, 'AAPL', 'alpha006'),
        (QuantAlpha158Value.__name__, 'AAPL', 'SUM60'),
        (QuantAlpha101Value.__name__, 'MSFT', 'alpha001'),
    }
    db.flush.assert_awaited_once()


def test_replace_alpha_values_bulk_skips_empty() -> None:
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    asyncio.run(QuantSnapshotDao.replace_alpha_values_bulk(db, []))
    db.execute.assert_not_called()
    db.flush.assert_not_called()
