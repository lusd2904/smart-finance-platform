import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.exit_rules import (
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TRAILING_ACTIVATE_PCT,
    TRAILING_STOP_PCT,
    ExitRuleConfig,
    clear_exit_peak,
    evaluate_position_exit,
    exit_peak_key,
    load_exit_peak,
    ratchet_peak,
    store_exit_peak,
)
from module_quant.service.snapshot_service import SnapshotService


def test_no_exit_inside_band() -> None:
    assert evaluate_position_exit(100, 100, 100) is None
    assert evaluate_position_exit(100, 104.9, 104.9) is None
    assert evaluate_position_exit(100, 107, 107) is None
    assert evaluate_position_exit(100, 92.1, 100) is None
    assert evaluate_position_exit(0, 100, 100) is None
    assert evaluate_position_exit(100, None, 100) is None
    assert evaluate_position_exit(None, 100, 100) is None


def test_hard_stop_at_minus_eight() -> None:
    hit = evaluate_position_exit(100, 92, 100)
    assert hit is not None
    assert hit.reason == 'stop_loss'
    assert hit.source == 'stop_loss'
    assert hit.pnl_pct == STOP_LOSS_PCT

    deeper = evaluate_position_exit(100, 91.5, 120)
    assert deeper is not None
    assert deeper.reason == 'stop_loss'


def test_take_profit_at_plus_fifteen() -> None:
    hit = evaluate_position_exit(100, 115, 115)
    assert hit is not None
    assert hit.reason == 'take_profit'
    assert hit.source == 'take_profit'
    assert hit.pnl_pct == TAKE_PROFIT_PCT

    above = evaluate_position_exit(100, 116, 125)
    assert above is not None
    assert above.reason == 'take_profit'


def test_trailing_activates_only_after_offset_then_fires_on_peak_drawdown() -> None:
    # Peak PnL 4.9% < 5% offset: 3%+ pullback from peak still holds.
    assert evaluate_position_exit(100, 101.7, 104.9) is None

    # Armed at +10% peak; 2.727% pullback (110 → 107) is below 3% of peak price.
    assert evaluate_position_exit(100, 107, 110) is None

    # 3% of peak 110 is 3.3; last 106.7 fires trailing (not cost-based 3%).
    hit = evaluate_position_exit(100, 106.7, 110)
    assert hit is not None
    assert hit.reason == 'trailing_stop'
    assert hit.source == 'trailing_stop'
    assert hit.peak == 110
    assert hit.drawdown_pct == TRAILING_STOP_PCT
    assert hit.peak_pnl_pct == 10.0


def test_peak_ratchet() -> None:
    assert ratchet_peak(None, 10) == 10
    assert ratchet_peak(0, 10) == 10
    assert ratchet_peak(-1, 10) == 10
    assert ratchet_peak(10, 12) == 12
    assert ratchet_peak(12, 11) == 12
    # last makes a new high → drawdown 0, trailing does not fire.
    assert evaluate_position_exit(100, 110, 105) is None
    fire = evaluate_position_exit(100, 106.7, 110)
    assert fire is not None
    assert fire.reason == 'trailing_stop'
    assert fire.peak == 110


def test_priority_stop_over_tp_over_trailing() -> None:
    # SL wins even when peak would also arm trailing.
    sl = evaluate_position_exit(100, 91, 130)
    assert sl is not None
    assert sl.reason == 'stop_loss'
    # TP wins over trailing when last is +15% and also off a higher peak.
    tp = evaluate_position_exit(100, 116, 130)
    assert tp is not None
    assert tp.reason == 'take_profit'


def test_settings_override_thresholds() -> None:
    rules = ExitRuleConfig.from_settings({'stop_loss_pct': -5.0, 'take_profit_pct': 8.0})
    assert rules.stop_loss_pct == -5.0
    assert rules.take_profit_pct == 8.0
    assert rules.trailing_activate_pct == TRAILING_ACTIVATE_PCT
    assert evaluate_position_exit(100, 95, 100, rules).reason == 'stop_loss'
    assert evaluate_position_exit(100, 108, 108, rules).reason == 'take_profit'


def test_exit_peak_key() -> None:
    assert exit_peak_key(7, 'US', 'AAPL') == 'sfp:exit:peak:7:US:AAPL'


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.ttls[key] = ttl

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)


def test_peak_redis_roundtrip() -> None:
    fake = _FakeRedis()

    async def _run() -> None:
        with patch('module_quant.service.exit_rules._redis', return_value=fake):
            assert await load_exit_peak(1, 'US', 'AAPL') is None
            await store_exit_peak(1, 'US', 'AAPL', 123.45)
            assert await load_exit_peak(1, 'US', 'AAPL') == 123.45
            assert fake.ttls[exit_peak_key(1, 'US', 'AAPL')] == 30 * 24 * 3600
            await clear_exit_peak(1, 'US', 'AAPL')
            assert await load_exit_peak(1, 'US', 'AAPL') is None

    asyncio.run(_run())


def _trade_settings(**overrides):
    data = {
        'user_id': 1,
        'auto_trade_enabled': True,
        'daily_buy_ratio': 0.20,
        'max_symbol_position_pct': 0.10,
        'has_keys': True,
    }
    data.update(overrides)
    return data


def _run_monitor(*, positions, settings=None, submit_ok=True, stored_peak=None):
    from module_quant.dao.quant_dao import QuantLongbridgeConfigDao
    from module_quant.service import snapshot_service as ss
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.dao.trade_dao import TradeDao
    from module_trade.service.auto_trade_service import AutoTradeService

    db = MagicMock()
    db.commit = AsyncMock()
    submit = AsyncMock(
        return_value={'ok': submit_ok, 'orderId': 'SIM-EXIT-1', 'message': 'ok' if submit_ok else 'fail'}
    )
    add_decision = AsyncMock()
    add_risk = AsyncMock()
    store_peak = AsyncMock()
    clear_peak = AsyncMock()
    load_peak = AsyncMock(return_value=stored_peak)

    async def _inner() -> tuple:
        with (
            patch.object(QuantLongbridgeConfigDao, 'list_configured_user_ids', AsyncMock(return_value=[1])),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(
                AutoTradeService, 'load_user_trade_settings', AsyncMock(return_value=settings or _trade_settings())
            ),
            patch.object(
                LongbridgeService,
                'get_positions_async',
                AsyncMock(return_value={'configured': True, 'positions': positions}),
            ),
            patch.object(LongbridgeService, 'submit_order_async', submit),
            patch.object(LongbridgeService, 'extract_order_id', return_value='SIM-EXIT-1'),
            patch.object(TradeDao, 'add_auto_trade_decision', add_decision),
            patch.object(TradeDao, 'list_risk_events', AsyncMock(return_value=[])),
            patch.object(TradeDao, 'add_risk_event', add_risk),
            patch.object(ss.QuantSnapshotDao, 'add_readmodel_snapshot', AsyncMock()),
            patch.object(ss.ReadModelService, 'put_scheduled', AsyncMock()),
            patch('module_quant.service.snapshot_service.load_exit_peak', load_peak),
            patch('module_quant.service.snapshot_service.store_exit_peak', store_peak),
            patch('module_quant.service.snapshot_service.clear_exit_peak', clear_peak),
        ):
            result = await SnapshotService.run_position_monitor(db)
        return result, submit, add_decision, add_risk, store_peak, clear_peak

    return asyncio.run(_inner())


def test_monitor_sells_on_stop_loss() -> None:
    result, submit, add_decision, add_risk, _store, clear_peak = _run_monitor(
        positions=[{'symbol': 'AAPL.US', 'market': 'US', 'quantity': 10, 'costPrice': 100, 'lastPrice': 91}],
    )
    assert result['soldCount'] == 1
    assert result['alertCount'] == 1
    submit.assert_awaited_once()
    assert submit.await_args.kwargs['side'] == 'SELL'
    assert add_decision.await_args.args[1]['source'] == 'stop_loss'
    assert add_risk.await_args.args[1]['event_level'] == 'danger'
    clear_peak.assert_awaited()


def test_monitor_sells_on_take_profit() -> None:
    result, submit, add_decision, add_risk, _store, clear_peak = _run_monitor(
        positions=[{'symbol': 'MSFT.US', 'market': 'US', 'quantity': 5, 'costPrice': 100, 'lastPrice': 116}],
    )
    assert result['soldCount'] == 1
    assert add_decision.await_args.args[1]['source'] == 'take_profit'
    assert '止盈' in add_risk.await_args.args[1]['title']
    submit.assert_awaited_once()
    clear_peak.assert_awaited()


def test_monitor_sells_on_trailing_stop() -> None:
    result, submit, add_decision, add_risk, _store, clear_peak = _run_monitor(
        positions=[{'symbol': 'NVDA.US', 'market': 'US', 'quantity': 3, 'costPrice': 100, 'lastPrice': 106.7}],
        stored_peak=110,
    )
    assert result['soldCount'] == 1
    assert add_decision.await_args.args[1]['source'] == 'trailing_stop'
    assert '移动止盈' in add_risk.await_args.args[1]['title']
    submit.assert_awaited_once()
    clear_peak.assert_awaited()


def test_monitor_holds_in_band_and_stores_peak() -> None:
    result, submit, add_decision, _risk, store_peak, clear_peak = _run_monitor(
        positions=[{'symbol': 'AAPL.US', 'market': 'US', 'quantity': 10, 'costPrice': 100, 'lastPrice': 104}],
        stored_peak=103,
    )
    assert result['soldCount'] == 0
    assert result['alertCount'] == 0
    submit.assert_not_awaited()
    add_decision.assert_not_awaited()
    store_peak.assert_awaited()
    assert store_peak.await_args.args[3] == 104
    clear_peak.assert_not_awaited()


def test_monitor_records_without_sell_when_auto_trade_off() -> None:
    result, submit, add_decision, add_risk, store_peak, clear_peak = _run_monitor(
        positions=[{'symbol': 'AAPL.US', 'market': 'US', 'quantity': 10, 'costPrice': 100, 'lastPrice': 91}],
        settings=_trade_settings(auto_trade_enabled=False),
    )
    assert result['soldCount'] == 0
    assert result['alertCount'] == 1
    submit.assert_not_awaited()
    add_decision.assert_not_awaited()
    add_risk.assert_awaited()
    assert '自动交易未开' in add_risk.await_args.args[1]['content']
    store_peak.assert_awaited()
    clear_peak.assert_not_awaited()


def test_monitor_clears_peak_when_qty_zero() -> None:
    result, submit, add_decision, add_risk, store_peak, clear_peak = _run_monitor(
        positions=[{'symbol': 'AAPL.US', 'market': 'US', 'quantity': 0, 'costPrice': 100, 'lastPrice': 91}],
    )
    assert result['soldCount'] == 0
    assert result['alertCount'] == 0
    submit.assert_not_awaited()
    add_decision.assert_not_awaited()
    add_risk.assert_not_awaited()
    store_peak.assert_not_awaited()
    clear_peak.assert_awaited()
