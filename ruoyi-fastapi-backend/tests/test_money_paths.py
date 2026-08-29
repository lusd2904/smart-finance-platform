"""资金路径单元测试：次日清单下单状态机、仓位计算、rebalance 卖出护栏、自动交易按用户隔离。"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.dao.quant_dao import QuantDailyListDao
from module_quant.service.daily_list_service import LOT, DailyListService
from module_trade.service.auto_trade_service import AutoTradeService


def _item(**kw):
    base = {
        'item_id': 1,
        'list_id': 10,
        'user_id': 101,
        'trade_date': '2026-08-24',
        'symbol': 'AAPL',
        'market': 'US',
        'name': 'Apple',
        'signal': 'BUY',
        'score': 80,
        'confidence': 85,
        'reason': 'test',
        'selected': '1',
        'auto_trade': '1',
        'status': 'listed',
        'side': 'BUY',
        'quantity': None,
        'price': 100.0,
        'order_id': None,
        'error': None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------- _place_or_queue ---


def test_place_or_queue_idempotent_when_already_submitted() -> None:
    row = _item(status='submitted', order_id='LB-123')

    async def _run() -> None:
        res = await DailyListService._place_or_queue(SimpleNamespace(), row, 101)
        assert res['ok'] is True
        assert res['idempotent'] is True
        assert res['orderId'] == 'LB-123'

    asyncio.run(_run())


def test_place_or_queue_skipped_row_never_resubmits() -> None:
    row = _item(status='skipped', error='非交易日禁止开仓')

    async def _run() -> None:
        res = await DailyListService._place_or_queue(SimpleNamespace(), row, 101)
        assert res['ok'] is False
        assert '已跳过' in res['message'] or '非交易日' in res['message']

    asyncio.run(_run())


def test_place_or_queue_queues_when_market_closed() -> None:
    row = _item(status='listed')

    async def _run() -> None:
        db = SimpleNamespace()
        with patch('module_quant.service.daily_list_service.is_market_session_open', return_value=False):
            res = await DailyListService._place_or_queue(db, row, 101, force_submit=False)
        assert res.get('queued') is True
        assert row.status == 'queued'

    asyncio.run(_run())


def test_place_or_queue_submits_and_records_order() -> None:
    row = _item(status='listed', price=0.0)

    async def _run() -> None:
        db = SimpleNamespace()
        with (
            patch('module_quant.service.daily_list_service.is_market_session_open', return_value=True),
            patch.object(DailyListService, '_size_order', AsyncMock(return_value=5)),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.submit_order_async',
                AsyncMock(return_value={'ok': True, 'orderId': 'LB-9'}),
            ) as submit,
        ):
            res = await DailyListService._place_or_queue(db, row, 101)
        submit.assert_awaited_once()
        assert row.status == 'submitted'
        assert row.order_id == 'LB-9'
        assert row.quantity == 5
        assert res['ok'] is True

    asyncio.run(_run())


def test_place_or_queue_rejected_records_error() -> None:
    row = _item(status='listed')

    async def _run() -> None:
        db = SimpleNamespace()
        with (
            patch('module_quant.service.daily_list_service.is_market_session_open', return_value=True),
            patch.object(DailyListService, '_size_order', AsyncMock(return_value=3)),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.submit_order_async',
                AsyncMock(return_value={'ok': False, 'message': '余额不足'}),
            ),
        ):
            res = await DailyListService._place_or_queue(db, row, 101)
        assert res['ok'] is False
        assert row.status == 'rejected'
        assert '余额不足' in (row.error or '')

    asyncio.run(_run())


def test_place_or_queue_zero_qty_skips() -> None:
    row = _item(status='listed')

    async def _run() -> None:
        db = SimpleNamespace()
        with (
            patch('module_quant.service.daily_list_service.is_market_session_open', return_value=True),
            patch.object(DailyListService, '_size_order', AsyncMock(return_value=0)),
        ):
            res = await DailyListService._place_or_queue(db, row, 101)
        assert res['ok'] is False
        assert row.status == 'skipped'
        assert '仓位' in (row.error or '')

    asyncio.run(_run())


# ---------------------------------------------------------------- _size_order ---


def test_size_order_caps_by_ratio_and_name_notional() -> None:
    row = _item(market='US', price=50.0)

    async def _run() -> None:
        # 净资产 100_000：15% 上限 15000，单票上限 8000 → 取 8000 → 160 股
        with patch(
            'module_quant.service.daily_list_service.LongbridgeService.get_account_balance_async',
            AsyncMock(return_value={'balances': [{'netAssets': 100_000}]}),
        ):
            qty = await DailyListService._size_order(row)
        assert qty == 160

    asyncio.run(_run())


def test_size_order_falls_back_to_lot_when_no_account() -> None:
    row = _item(market='HK', price=0.0)

    async def _run() -> None:
        with patch(
            'module_quant.service.daily_list_service.LongbridgeService.get_account_balance_async',
            AsyncMock(return_value={'balances': []}),
        ), patch(
            'module_quant.service.daily_list_service.LongbridgeService.get_realtime_quote',
            return_value={'quotes': []},
        ):
            qty = await DailyListService._size_order(row)
        assert qty == LOT['HK']

    asyncio.run(_run())


def test_size_order_uses_quote_price_when_missing() -> None:
    row = _item(market='US', price=0.0)

    async def _run() -> None:
        with patch(
            'module_quant.service.daily_list_service.LongbridgeService.get_account_balance_async',
            AsyncMock(return_value={'balances': [{'netAssets': 10_000}]}),
        ), patch(
            'module_quant.service.daily_list_service.LongbridgeService.get_realtime_quote',
            return_value={'quotes': [{'lastDone': 200.0}]},
        ):
            qty = await DailyListService._size_order(row)
        # min(1500, 8000)=1500 / 200 = 7 股
        assert qty == 7

    asyncio.run(_run())


# ------------------------------------------------------------- rebalance 护栏 ---


def test_rebalance_only_sells_auto_bought_symbols() -> None:
    """清单外但非自动买入的持仓（如手动买的 TSLA）绝不能被自动卖掉。"""

    async def _run() -> None:
        latest = SimpleNamespace(list_id=10, auto_enabled='1')
        items = [_item(item_id=1, symbol='AAPL', market='US', auto_trade='1')]
        positions = [
            {'symbol': 'TSLA.US', 'quantity': 10},  # 清单外 + 非自动买入 → 护栏必须跳过
            {'symbol': 'NVDA.US', 'quantity': 5},  # 清单外 + 曾自动买入 → 允许卖出
        ]
        db = SimpleNamespace()
        with (
            patch('module_quant.service.daily_list_service.QuantDailyListDao.latest_for_user', AsyncMock(return_value=latest)),
            patch('module_quant.service.daily_list_service.QuantDailyListDao.list_items', AsyncMock(return_value=items)),
            patch.object(QuantDailyListDao, 'auto_bought_symbols', AsyncMock(return_value={('NVDA', 'US')})),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.get_positions_async',
                AsyncMock(return_value={'positions': positions}),
            ),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.submit_order_async',
                AsyncMock(return_value={'ok': True, 'orderId': 'S1'}),
            ) as submit,
            patch.object(DailyListService, '_place_or_queue', AsyncMock(return_value={'itemId': 1, 'ok': True})),
            patch.object(DailyListService, '_account_trade_ready', AsyncMock(return_value=(True, ''))),
            patch('module_quant.service.daily_list_service.LongbridgeService.ensure_credentials_from_db', AsyncMock()),
        ):
            db.commit = AsyncMock()
            res = await DailyListService.rebalance_auto(db, 101)

        sold = [o for o in res['outcomes'] if o.get('side') == 'SELL']
        assert [s['symbol'] for s in sold] == ['NVDA']  # 只卖了自动买入过的
        guard_symbols = {g['symbol'] for g in res.get('guardSkipped', [])}
        assert 'TSLA' in guard_symbols
        assert submit.await_count == 1

    asyncio.run(_run())


def test_rebalance_never_sells_current_wanted_positions() -> None:

    async def _run() -> None:
        latest = SimpleNamespace(list_id=10, auto_enabled='1')
        items = [_item(item_id=1, symbol='AAPL', market='US', auto_trade='1')]
        positions = [{'symbol': 'AAPL.US', 'quantity': 8}]  # 在清单内 → 不卖
        db = SimpleNamespace()
        with (
            patch('module_quant.service.daily_list_service.QuantDailyListDao.latest_for_user', AsyncMock(return_value=latest)),
            patch('module_quant.service.daily_list_service.QuantDailyListDao.list_items', AsyncMock(return_value=items)),
            patch.object(QuantDailyListDao, 'auto_bought_symbols', AsyncMock(return_value={('AAPL', 'US')})),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.get_positions_async',
                AsyncMock(return_value={'positions': positions}),
            ),
            patch(
                'module_quant.service.daily_list_service.LongbridgeService.submit_order_async',
                AsyncMock(),
            ) as submit,
            patch.object(DailyListService, '_place_or_queue', AsyncMock(return_value={'itemId': 1, 'ok': True})),
            patch.object(DailyListService, '_account_trade_ready', AsyncMock(return_value=(True, ''))),
            patch('module_quant.service.daily_list_service.LongbridgeService.ensure_credentials_from_db', AsyncMock()),
        ):
            db.commit = AsyncMock()
            res = await DailyListService.rebalance_auto(db, 101)

        assert not [o for o in res['outcomes'] if o.get('side') == 'SELL']
        submit.assert_not_awaited()

    asyncio.run(_run())


def test_rebalance_skips_when_auto_disabled() -> None:

    async def _run() -> None:
        db = SimpleNamespace()
        with patch(
            'module_quant.service.daily_list_service.QuantDailyListDao.latest_for_user',
            AsyncMock(return_value=SimpleNamespace(list_id=10, auto_enabled='0')),
        ):
            res = await DailyListService.rebalance_auto(db, 101)
        assert res == {'skipped': True, 'reason': 'auto_disabled'}

    asyncio.run(_run())


def test_rebalance_skips_when_account_switch_off() -> None:

    async def _run() -> None:
        db = SimpleNamespace()
        with (
            patch(
                'module_quant.service.daily_list_service.QuantDailyListDao.latest_for_user',
                AsyncMock(return_value=SimpleNamespace(list_id=10, auto_enabled='1')),
            ),
            patch.object(
                DailyListService,
                '_account_trade_ready',
                AsyncMock(return_value=(False, '请先在「量化交易 / 策略配置」打开本账户自动交易')),
            ),
        ):
            res = await DailyListService.rebalance_auto(db, 101)
        assert res['skipped'] is True
        assert res['reason'] == 'account_auto_disabled'

    asyncio.run(_run())


# ------------------------------------------------------- 自动交易按用户隔离 ---


def test_resolve_targets_scopes_to_user_watchlist() -> None:
    from module_market.dao.market_dao import MarketWatchlistDao

    rows = [SimpleNamespace(symbol='AAPL', market='US'), SimpleNamespace(symbol='0700.HK', market='HK')]

    async def _run() -> None:
        db = SimpleNamespace()
        with (
            patch.object(AutoTradeService, '_heat_scan_universe', AsyncMock(return_value=[])),
            patch.object(MarketWatchlistDao, 'get_enabled', AsyncMock(return_value=rows)) as get_rows,
        ):
            items = await AutoTradeService._resolve_targets(db, None, user_id=42)
        get_rows.assert_awaited_once_with(db, user_id=42)
        assert items == [{'symbol': 'AAPL', 'market': 'US'}, {'symbol': '0700', 'market': 'HK'}]

    asyncio.run(_run())


def test_resolve_targets_explicit_symbols_bypass_watchlist() -> None:

    async def _run() -> None:
        db = SimpleNamespace()
        items = await AutoTradeService._resolve_targets(db, ['nvda.us'], user_id=42)
        assert items == [{'symbol': 'NVDA', 'market': 'US'}]

    asyncio.run(_run())


def test_run_cycle_passes_user_id_to_targets_credentials_and_log() -> None:
    from module_quant.service.longbridge_service import LongbridgeService
    from module_trade.dao.trade_dao import TradeDao

    async def _run() -> None:
        db = SimpleNamespace()
        db.commit = AsyncMock()
        with (
            patch.object(AutoTradeService, '_resolve_targets', AsyncMock(return_value=[])) as resolve,
            patch.object(
                AutoTradeService,
                'load_user_trade_settings',
                AsyncMock(return_value={'user_id': 77, 'auto_trade_enabled': False, 'daily_buy_ratio': 0.20}),
            ),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()) as ensure,
            patch.object(TradeDao, 'add_ai_trade_run_log', AsyncMock()) as add_log,
        ):
            res = await AutoTradeService.run_watchlist_strategy_cycle(db, source='scheduler', user_id=77)
        resolve.assert_awaited_once()
        assert resolve.await_args.kwargs.get('user_id') == 77
        ensure.assert_awaited_once()
        assert ensure.await_args.args[-1] == 77
        assert add_log.await_args.args[1]['user_id'] == 77
        assert res['submittedOrdersCount'] == 0

    asyncio.run(_run())


def test_today_stats_filters_by_user() -> None:
    """_today_stats 的 SQL 必须带 user_id 过滤（护栏按账户隔离）。"""
    import inspect

    src = inspect.getsource(AutoTradeService._today_stats)
    assert 'user_id' in src
    assert 'PlatAutoTradeDecision.user_id ==' in src
