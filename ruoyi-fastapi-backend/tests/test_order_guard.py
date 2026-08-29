"""手工下单护栏与紧急停机。"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_trade.service.order_guard import (
    buy_blocked_reason,
    halt_block_reason,
    is_buy_side,
    normalize_side,
    order_notional,
    sell_blocked_reason,
    today_buy_notional_from_orders,
    write_halt,
)
from module_trade.service.trade_service import TradeService


def setup_function() -> None:
    asyncio.run(write_halt(halted=False, reason='', user_id=None))


def test_side_and_notional_helpers() -> None:
    assert normalize_side('BUY') == 'buy'
    assert normalize_side('卖出') == 'sell'
    assert is_buy_side('b') is True
    assert is_buy_side('SELL') is False
    assert order_notional(10, 12.5) == 125.0
    assert order_notional(0, 10) == 0.0


def test_today_buy_notional_skips_cancelled() -> None:
    count, notional = today_buy_notional_from_orders(
        [
            {'side': 'Buy', 'status': 'submitted', 'quantity': 10, 'price': 100},
            {'side': 'Buy', 'status': 'cancelled', 'quantity': 50, 'price': 100},
            {'side': 'Sell', 'status': 'submitted', 'quantity': 8, 'price': 90},
            {'side': 'Buy', 'status': 'filled', 'quantity': 2, 'price': 50},
        ]
    )
    assert count == 3
    assert notional == 10 * 100 + 2 * 50


def test_buy_blocked_by_daily_cap_and_cash() -> None:
    daily = buy_blocked_reason(
        notional=3000,
        net_assets=10000,
        available_cash=8000,
        total_mv=1000,
        existing_mv=0,
        today_notional=0,
        daily_buy_ratio=0.20,
        max_symbol_pct=0.10,
    )
    assert daily is not None
    assert '日内' in daily

    cash = buy_blocked_reason(
        notional=800,
        net_assets=10000,
        available_cash=100,
        total_mv=0,
        existing_mv=0,
        today_notional=0,
        daily_buy_ratio=0.20,
        max_symbol_pct=0.10,
    )
    assert cash is not None
    assert '现金' in cash


def test_buy_blocked_by_symbol_and_gross_cap() -> None:
    symbol = buy_blocked_reason(
        notional=600,
        net_assets=10000,
        available_cash=8000,
        total_mv=500,
        existing_mv=900,
        today_notional=0,
        daily_buy_ratio=0.20,
        max_symbol_pct=0.10,
    )
    assert symbol is not None
    assert '单标的' in symbol

    gross = buy_blocked_reason(
        notional=200,
        net_assets=10000,
        available_cash=8000,
        total_mv=9900,
        existing_mv=0,
        today_notional=0,
        daily_buy_ratio=0.20,
        max_symbol_pct=0.10,
    )
    assert gross is not None
    assert '净资产' in gross


def test_buy_passes_inside_caps() -> None:
    assert (
        buy_blocked_reason(
            notional=400,
            net_assets=10000,
            available_cash=8000,
            total_mv=1000,
            existing_mv=200,
            today_notional=100,
            daily_buy_ratio=0.20,
            max_symbol_pct=0.10,
        )
        is None
    )


def test_sell_blocked_without_position() -> None:
    assert sell_blocked_reason(quantity=10, available_qty=0) is not None
    assert sell_blocked_reason(quantity=12, available_qty=10) is not None
    assert sell_blocked_reason(quantity=5, available_qty=10) is None


def test_halt_blocks_and_clears() -> None:
    async def _run() -> None:
        await write_halt(halted=True, reason='测试停机', user_id=1)
        msg = await halt_block_reason()
        assert msg is not None
        assert '停机' in msg
        await write_halt(halted=False, reason='', user_id=1)
        assert await halt_block_reason() is None

    asyncio.run(_run())


def test_submit_order_short_circuits_when_guard_blocks() -> None:
    async def _run() -> None:
        db = AsyncMock()
        with (
            patch.object(TradeService, '_ensure', AsyncMock()),
            patch(
                'module_trade.service.order_guard.evaluate_manual_order',
                AsyncMock(return_value={'ok': False, 'blocked': True, 'message': '紧急停机中，禁止新委托'}),
            ),
            patch.object(TradeService, 'push_notification_db', AsyncMock()) as notice,
            patch(
                'module_quant.service.longbridge_service.LongbridgeService.submit_order_async',
                AsyncMock(),
            ) as submit,
        ):
            result = await TradeService.submit_order_services(
                db, symbol='AAPL', side='buy', quantity=10, price=100, market='US', user_id=1
            )
        assert result['ok'] is False
        assert result['blocked'] is True
        submit.assert_not_called()
        notice.assert_awaited()

    asyncio.run(_run())
