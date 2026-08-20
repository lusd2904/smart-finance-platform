import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.longbridge_service import LongbridgeService
from module_trade.service.auto_trade_service import (
    check_daily_limits,
    merge_runtime_config,
    parse_symbol_market,
    resolve_submit_permission,
    slippage_exceeded,
)


def test_default_config_is_scan_only() -> None:
    config = merge_runtime_config(None)
    assert config['auto_execute'] is False
    assert config['require_paper'] is True


def test_client_cannot_disable_paper_or_raise_limits() -> None:
    config = merge_runtime_config(
        {
            'require_paper': False,
            'auto_execute': True,
            'max_daily_orders': 999,
            'max_daily_notional_amount': 1_000_000,
            'max_symbols': 99,
            'min_confidence': 80,
        }
    )
    assert config['require_paper'] is True
    assert config['auto_execute'] is False
    assert config['max_daily_orders'] == 10
    assert config['max_daily_notional_amount'] == 6000.0
    assert config['max_symbols'] == 20
    assert config['min_confidence'] == 80


def test_submit_permission_requires_all_gates() -> None:
    allowed, reason = resolve_submit_permission(execute=False, trading_enabled=True, require_paper=False)
    assert allowed is False
    assert '扫描' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, trading_enabled=True, require_paper=True)
    assert allowed is False
    assert '纸账户' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, trading_enabled=False, require_paper=False)
    assert allowed is False
    assert '开关' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, trading_enabled=True, require_paper=False)
    assert allowed is True
    assert reason is None


def test_daily_limits_and_slippage() -> None:
    assert check_daily_limits(10, 10, 0, 6000)
    assert check_daily_limits(0, 10, 6000, 6000)
    assert check_daily_limits(1, 10, 100, 6000) is None
    assert slippage_exceeded(100, 0, 0.03) is True
    assert slippage_exceeded(100, 104, 0.03) is True
    assert slippage_exceeded(100, 101, 0.03) is False


def test_symbol_and_order_id_helpers() -> None:
    assert parse_symbol_market('NVDA.US') == ('NVDA', 'US')
    assert parse_symbol_market('0700.HK') == ('0700', 'HK')
    assert parse_symbol_market('AAPL') == ('AAPL', 'US')
    assert LongbridgeService.to_longbridge_symbol('AAPL', 'US') == 'AAPL.US'
    assert LongbridgeService.extract_last_price({'quotes': [{'symbol': 'AAPL.US', 'lastDone': 190.5}]}, 'AAPL') == 190.5
    assert LongbridgeService.extract_order_id({'ok': True, 'orderId': 'abc'}) == 'abc'
    assert LongbridgeService.extract_order_id({'ok': True, 'data': {'order_id': 'xyz'}}) == 'xyz'
    assert LongbridgeService.extract_order_id({'ok': False, 'orderId': 'abc'}) is None
    flat = LongbridgeService.flatten_account(
        {'configured': True, 'balances': [{'totalCash': 10, 'availableCash': 8, 'netAssets': 12, 'currency': 'USD'}]}
    )
    assert flat['netAssets'] == 12
    assert flat['availableCash'] == 8


def test_cycle_never_submits_when_execute_false_or_paper_on() -> None:
    from module_quant.service.strategy_service import StrategyService
    from module_trade.dao.trade_dao import TradeDao
    from module_trade.service.auto_trade_service import AutoTradeService

    signals = {
        'signals': [
            {
                'symbol': 'AAPL',
                'market': 'US',
                'signal': 'BUY',
                'confidence': 88,
                'score': 88,
                'price': 100,
                'reason': 'ok',
                'factor_json': {},
            }
        ]
    }

    async def _run(execute: bool) -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        with (
            patch.object(AutoTradeService, '_resolve_targets', AsyncMock(return_value=[{'symbol': 'AAPL', 'market': 'US'}])),
            patch.object(StrategyService, 'run_strategy_cycle_async', AsyncMock(return_value=signals)),
            patch.object(AutoTradeService, '_today_stats', AsyncMock(return_value=(0, 0.0))),
            patch.object(TradeDao, 'add_ai_trade_run_log', AsyncMock()),
            patch.object(TradeDao, 'add_auto_trade_decision', AsyncMock()) as add_decision,
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
            patch.object(LongbridgeService, 'submit_order_async', AsyncMock()) as submit,
        ):
            result = await AutoTradeService.run_watchlist_strategy_cycle(db, execute=execute)
            submit.assert_not_called()
            add_decision.assert_not_called()
            assert result['submittedOrdersCount'] == 0

    asyncio.run(_run(False))
    asyncio.run(_run(True))
