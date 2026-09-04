import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.quote_subscribe_hub import QuoteSubscribeHub
from module_quant.service.longbridge.fx import (
    FALLBACK_USD_HKD,
    FxRates,
    pick_available_cash_usd,
    pick_net_assets_usd,
)
from module_quant.service.longbridge_service import LongbridgeService
from module_trade.service.auto_trade_service import (
    AutoTradeService,
    as_alpha_factor_dict,
    check_daily_limits,
    clamp_max_symbol_position_pct,
    daily_buy_cap,
    is_auto_trade_market,
    match_position,
    merge_runtime_config,
    parse_symbol_market,
    quote_opportunity_window,
    remaining_gross_room,
    resolve_submit_permission,
    round_limit_price,
    should_skip_duplicate_buy,
    should_skip_held_buy,
    slim_scan_row,
    slippage_exceeded,
    symbol_buy_room,
    symbol_position_cap,
    total_position_market_value,
    zero_nav_skip_reason,
)


def setup_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def teardown_function() -> None:
    QuoteSubscribeHub.reset_for_tests()


def test_default_config_is_scan_only() -> None:
    config = merge_runtime_config(None)
    assert config['auto_execute'] is False
    assert 'require_paper' not in config


def test_client_cannot_raise_limits_or_enable_auto_execute() -> None:
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
    assert 'require_paper' not in config
    assert config['auto_execute'] is False
    assert config['max_daily_orders'] == 10
    assert config['max_daily_notional_amount'] == 0.0
    assert config['max_symbols'] == 20
    assert config['min_confidence'] == 80
    assert config['max_position_ratio'] == 0.20


def test_submit_permission_only_needs_execute_and_credentials() -> None:
    allowed, reason = resolve_submit_permission(execute=False)
    assert allowed is False
    assert '扫描' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, configured=False)
    assert allowed is False
    assert '凭据' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, configured=True)
    assert allowed is False
    assert '未开启自动交易' in (reason or '')

    allowed, reason = resolve_submit_permission(execute=True, configured=True, auto_trade_enabled=True)
    assert allowed is True
    assert reason is None


def test_daily_limits_and_slippage() -> None:
    assert check_daily_limits(10, 10, 0, 6000)
    assert check_daily_limits(0, 10, 6000, 6000)
    assert check_daily_limits(1, 10, 100, 6000) is None
    assert slippage_exceeded(100, 0, 0.03) is True
    assert slippage_exceeded(100, 104, 0.03) is True
    assert slippage_exceeded(100, 101, 0.03) is False
    assert daily_buy_cap(10000) == 2000.0
    assert daily_buy_cap(0) == 0.0
    assert clamp_max_symbol_position_pct(None) == 0.10
    assert clamp_max_symbol_position_pct(0.01) == 0.05
    assert clamp_max_symbol_position_pct(0.40) == 0.30
    assert symbol_position_cap(10000, 0.10) == 1000.0
    assert symbol_buy_room(10000, 0.10, 0) == 1000.0
    assert symbol_buy_room(10000, 0.10, 1200) == -200.0
    assert should_skip_duplicate_buy('AAPL', {'AAPL'}) is True
    assert should_skip_duplicate_buy('AAPL.US', {'AAPL'}) is True
    assert should_skip_duplicate_buy('MSFT', {'AAPL'}) is False
    assert is_auto_trade_market('US') is True
    assert is_auto_trade_market('HK') is True
    assert is_auto_trade_market('CN', '600519') is False
    assert is_auto_trade_market('SH', '600519.SH') is False
    assert should_skip_held_buy({'symbol': 'AAPL.US', 'quantity': 1}) is True
    assert should_skip_held_buy({'symbol': 'AAPL.US', 'quantity': 0}) is False
    assert total_position_market_value(
        [{'marketValue': 6000}, {'quantity': 10, 'costPrice': 100}]
    ) == 7000.0
    assert remaining_gross_room(10000, 12000) < 0
    assert remaining_gross_room(10000, 2000) == 8000.0
    held = match_position([{'symbol': '00700.HK', 'quantity': 100}], '700', 'HK')
    assert held is not None
    assert match_position([{'symbol': 'AAPL.US', 'quantity': 2}], 'AAPL', 'US') is not None
    assert round_limit_price(1247.665, 'US') == 1247.67
    assert round_limit_price(10.004, 'US') == 10.00
    slim = slim_scan_row({'symbol': 'AAPL', 'factors': {'alpha158Count': 154}, 'score': 88, 'signal': 'BUY'})
    assert 'factors' not in slim
    assert slim['score'] == {'total': 88}


def test_quote_window_and_alpha_payload_helpers() -> None:
    assert quote_opportunity_window(['a', 'b', 'c', 'd'], 3) == ['a', 'b', 'c', 'd']
    assert len(quote_opportunity_window(list(range(20)), 3)) == 15
    assert as_alpha_factor_dict({'alpha006': 0.1}) == {'alpha006': 0.1}
    assert as_alpha_factor_dict(0.42) == {}
    assert as_alpha_factor_dict(None) == {}
    assert 'circuit_open' in zero_nav_skip_reason(0.2, {'reason': 'circuit_open', 'message': ''})
    assert '熔断' in zero_nav_skip_reason(0.2, {'reason': 'circuit_open', 'message': '长桥熔断中'})
    assert '净资产为 0' in zero_nav_skip_reason(0.2, {'balances': []})


def test_fx_converts_hkd_balances_to_usd_nav() -> None:
    fx = FxRates(usd_hkd=7.8, usd_cny=7.2, sources={'USDHKD': 'test', 'USDCNH': 'test'})
    account = {
        'configured': True,
        'balances': [{'currency': 'HKD', 'netAssets': 3_865_000, 'availableCash': 500_000, 'totalCash': 500_000}],
    }
    nav_usd = pick_net_assets_usd(account, fx)
    cash_usd = pick_available_cash_usd(account, fx)
    assert nav_usd == round(3_865_000 / 7.8, 2)
    assert cash_usd == round(500_000 / 7.8, 2)
    assert symbol_position_cap(nav_usd, 0.10) == round(nav_usd * 0.10, 2)
    # 错误行为：把 HKD 当 USD 会得到 386500 的单票上限
    assert symbol_position_cap(3_865_000, 0.10) > 300_000


def test_fx_mixed_hkd_usd_balances_sum_in_usd() -> None:
    fx = FxRates(usd_hkd=7.8, usd_cny=7.2)
    account = {
        'configured': True,
        'balances': [
            {'currency': 'HKD', 'netAssets': 780_000, 'availableCash': 78_000, 'totalCash': 78_000},
            {'currency': 'USD', 'netAssets': 10_000, 'availableCash': 5_000, 'totalCash': 5_000},
        ],
    }
    assert pick_net_assets_usd(account, fx) == 110_000.0
    assert pick_available_cash_usd(account, fx) == 15_000.0


def test_position_market_value_converts_hkd_to_usd() -> None:
    from module_trade.service.auto_trade_service import existing_position_market_value

    fx = FxRates(usd_hkd=7.8)
    pos = {'symbol': '00700.HK', 'currency': 'HKD', 'quantity': 100, 'costPrice': 390}
    assert existing_position_market_value(pos, 400.0, fx) == round(40_000 / 7.8, 2)


def test_fx_hk_order_amount_from_usd_cap() -> None:
    fx = FxRates(usd_hkd=7.8)
    cap_usd = symbol_position_cap(10_000, 0.10)
    hkd_budget = fx.from_usd(cap_usd, 'HKD')
    assert hkd_budget == 7_800.0
    assert int(hkd_budget / 400) == 19


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


BUY_SIGNAL = {
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


async def _run_buy_cycle(
    *,
    positions=None,
    today_bought=None,
    settings=None,
    account_balance=None,
    fx=None,
    signal=None,
    targets=None,
    quote_result=None,
    custom_config=None,
):
    from module_quant.service.strategy_service import StrategyService
    from module_trade.dao.trade_dao import TradeDao
    from module_trade.service.auto_trade_service import AutoTradeService

    db = MagicMock()
    db.commit = AsyncMock()
    submit = AsyncMock(return_value={'ok': True, 'orderId': 'SIM-1'})
    add_decision = AsyncMock()
    fx_rates = fx or FxRates(usd_hkd=FALLBACK_USD_HKD, usd_cny=7.2, sources={'USDHKD': 'test', 'USDCNH': 'test'})
    balance = account_balance or {
        'configured': True,
        'balances': [{'currency': 'USD', 'netAssets': 10000, 'availableCash': 8000, 'totalCash': 8000}],
    }
    scan_signal = signal or BUY_SIGNAL
    target_items = targets or [{'symbol': 'AAPL', 'market': 'US'}]
    quotes = quote_result if quote_result is not None else {'quotes': [{'symbol': 'AAPL.US', 'lastDone': 100}]}
    with (
        patch.object(AutoTradeService, '_resolve_targets', AsyncMock(return_value=target_items)),
        patch.object(StrategyService, 'run_strategy_cycle_async', AsyncMock(return_value=scan_signal)),
        patch.object(AutoTradeService, '_today_stats', AsyncMock(return_value=(0, 0.0))),
        patch.object(AutoTradeService, '_today_bought_symbols', AsyncMock(return_value=set(today_bought or []))),
        patch.object(TradeDao, 'add_ai_trade_run_log', AsyncMock()),
        patch.object(TradeDao, 'add_auto_trade_decision', add_decision),
        patch('module_quant.dao.quant_dao.QuantSnapshotDao.replace_alpha_values', AsyncMock()),
        patch('module_quant.service.quant_service.QuantService.load_profile_config', AsyncMock(return_value={})),
        patch.object(AutoTradeService, 'load_user_trade_settings', AsyncMock(return_value=settings or _trade_settings())),
        patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(
            LongbridgeService,
            'get_positions_async',
            AsyncMock(return_value={'configured': True, 'positions': positions or []}),
        ),
        patch.object(LongbridgeService, 'get_account_balance_async', AsyncMock(return_value=balance)),
        patch('module_trade.service.auto_trade_service.load_fx_rates_async', AsyncMock(return_value=fx_rates)),
        patch.object(LongbridgeService, 'get_realtime_quote', return_value=quotes),
        patch.object(LongbridgeService, 'submit_order_async', submit),
        patch.object(LongbridgeService, 'extract_order_id', return_value='SIM-1'),
    ):
        result = await AutoTradeService.run_watchlist_strategy_cycle(
            db, execute=True, custom_config=custom_config
        )
    return result, submit, add_decision


def test_cycle_hkd_only_nav_does_not_size_us_buys_as_usd() -> None:
    async def _run() -> None:
        fx = FxRates(usd_hkd=7.8, usd_cny=7.2, sources={'USDHKD': 'test', 'USDCNH': 'test'})
        account = {
            'configured': True,
            'balances': [
                {'currency': 'HKD', 'netAssets': 3_865_000, 'availableCash': 3_865_000, 'totalCash': 3_865_000},
            ],
        }
        result, submit, _ = await _run_buy_cycle(
            account_balance=account,
            fx=fx,
            settings=_trade_settings(daily_buy_ratio=0.2, max_symbol_position_pct=0.1),
        )
        submit.assert_called_once()
        nav_usd = round(3_865_000 / 7.8, 2)
        per_symbol_cap = round(nav_usd * 0.10, 2)
        qty = submit.call_args.kwargs.get('quantity')
        assert qty == int(per_symbol_cap / 100)
        assert qty < 600
        assert result['guardrailSnapshot']['netAssetsUsd'] == nav_usd
        assert result['guardrailSnapshot']['balanceByCurrency'][0]['currency'] == 'HKD'
        assert result['guardrailSnapshot']['fxRates']['USDHKD'] == 7.8

    asyncio.run(_run())


def test_cycle_hk_stock_order_qty_uses_hkd_notional() -> None:
    hk_signal = {
        'signals': [
            {
                'symbol': '0700',
                'market': 'HK',
                'signal': 'BUY',
                'confidence': 88,
                'score': 88,
                'price': 400,
                'reason': 'ok',
                'factor_json': {},
            }
        ]
    }

    async def _run() -> None:
        fx = FxRates(usd_hkd=7.8, usd_cny=7.2)
        _, submit, _ = await _run_buy_cycle(
            fx=fx,
            signal=hk_signal,
            targets=[{'symbol': '0700', 'market': 'HK'}],
            quote_result={'quotes': [{'symbol': '0700.HK', 'lastDone': 400.0}]},
        )
        submit.assert_called_once()
        assert submit.call_args.kwargs.get('market') == 'HK'
        assert submit.call_args.kwargs.get('quantity') == 19

    asyncio.run(_run())


def test_cycle_mixed_hkd_usd_nav_sizes_from_converted_total() -> None:
    async def _run() -> None:
        fx = FxRates(usd_hkd=7.8, usd_cny=7.2)
        account = {
            'configured': True,
            'balances': [
                {'currency': 'HKD', 'netAssets': 780_000, 'availableCash': 780_000, 'totalCash': 780_000},
                {'currency': 'USD', 'netAssets': 10_000, 'availableCash': 10_000, 'totalCash': 10_000},
            ],
        }
        result, submit, _ = await _run_buy_cycle(account_balance=account, fx=fx)
        submit.assert_called_once()
        assert result['guardrailSnapshot']['netAssetsUsd'] == 110_000.0
        assert submit.call_args.kwargs.get('quantity') == 110

    asyncio.run(_run())


def test_cycle_never_submits_when_execute_false() -> None:
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

    async def _run() -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        with (
            patch.object(AutoTradeService, '_resolve_targets', AsyncMock(return_value=[{'symbol': 'AAPL', 'market': 'US'}])),
            patch.object(StrategyService, 'run_strategy_cycle_async', AsyncMock(return_value=signals)),
            patch.object(AutoTradeService, '_today_stats', AsyncMock(return_value=(0, 0.0))),
            patch.object(TradeDao, 'add_ai_trade_run_log', AsyncMock()),
            patch.object(TradeDao, 'add_auto_trade_decision', AsyncMock()) as add_decision,
            patch('module_quant.dao.quant_dao.QuantSnapshotDao.replace_alpha_values', AsyncMock()),
            patch('module_quant.service.quant_service.QuantService.load_profile_config', AsyncMock(return_value={})),
            patch.object(
                AutoTradeService,
                'load_user_trade_settings',
                AsyncMock(return_value=_trade_settings(auto_trade_enabled=False)),
            ),
            patch.object(LongbridgeService, 'ensure_credentials_from_db', AsyncMock()),
            patch.object(LongbridgeService, 'is_configured', return_value=True),
            patch.object(
                LongbridgeService,
                'get_account_balance_async',
                AsyncMock(
                return_value={
                    'configured': True,
                    'balances': [{'currency': 'USD', 'netAssets': 10000, 'availableCash': 8000, 'totalCash': 8000}],
                }
            ),
            ),
            patch('module_trade.service.auto_trade_service.load_fx_rates_async', AsyncMock(return_value=FxRates())),
            patch.object(LongbridgeService, 'submit_order_async', AsyncMock()) as submit,
        ):
            result = await AutoTradeService.run_watchlist_strategy_cycle(db, execute=False)
            submit.assert_not_called()
            add_decision.assert_not_called()
            assert result['submittedOrdersCount'] == 0

    asyncio.run(_run())


def test_cycle_submits_order_when_execute_true() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle()
        submit.assert_called_once()
        assert 'allow_sim' not in submit.call_args.kwargs
        # 10k NAV × 10% 单票上限 = 1000，不是日内 20% 的 2000
        assert submit.call_args.kwargs.get('quantity') == 10
        add_decision.assert_called_once()
        assert result['submittedOrdersCount'] == 1
        assert result['guardrailSnapshot']['maxDailyNotionalAmount'] == 2000.0
        assert result['guardrailSnapshot']['maxAmountPerSymbol'] == 1000.0
        assert result['guardrailSnapshot']['maxSymbolPositionPct'] == 0.10

    asyncio.run(_run())


def test_cycle_skips_buy_when_symbol_position_cap_reached() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(
            positions=[{'symbol': 'AAPL.US', 'quantity': 12, 'costPrice': 100, 'marketValue': 1200}],
        )
        submit.assert_not_called()
        add_decision.assert_not_called()
        assert result['submittedOrdersCount'] == 0
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '已持有该标的' in reasons or '单标的仓位上限' in reasons

    asyncio.run(_run())


def test_cycle_skips_buy_when_already_held() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(
            positions=[{'symbol': 'AAPL.US', 'quantity': 2, 'marketValue': 200}],
        )
        submit.assert_not_called()
        add_decision.assert_not_called()
        assert result['submittedOrdersCount'] == 0
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '已持有该标的' in reasons

    asyncio.run(_run())


def _ranked_buy_signals(*symbols: str) -> dict:
    confidence = 95
    return {
        'signals': [
            {
                'symbol': symbol,
                'market': 'US',
                'signal': 'BUY',
                'confidence': confidence - idx,
                'score': confidence - idx,
                'price': 100,
                'reason': 'ok',
                'factor_json': {},
            }
            for idx, symbol in enumerate(symbols)
        ]
    }


def test_cycle_skips_held_top_n_and_submits_next_unheld() -> None:
    symbols = ('AAPL', 'MSFT', 'NVDA', 'ZS', 'QQQ')
    quotes = {'quotes': [{'symbol': f'{code}.US', 'lastDone': 100} for code in symbols]}

    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(
            positions=[
                {'symbol': 'AAPL.US', 'quantity': 2, 'marketValue': 200},
                {'symbol': 'MSFT.US', 'quantity': 2, 'marketValue': 200},
                {'symbol': 'NVDA.US', 'quantity': 2, 'marketValue': 200},
            ],
            signal=_ranked_buy_signals(*symbols),
            targets=[{'symbol': code, 'market': 'US'} for code in symbols],
            quote_result=quotes,
            custom_config={'max_symbols': 3},
        )
        submitted = [call.kwargs.get('symbol') for call in submit.call_args_list]
        assert submitted == ['ZS', 'QQQ']
        assert result['submittedOrdersCount'] == 2
        assert add_decision.await_count == 2
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '已持有该标的' in reasons

    asyncio.run(_run())


def test_cycle_stops_after_max_symbols_orders() -> None:
    symbols = ('AAPL', 'MSFT', 'NVDA', 'ZS', 'QQQ')
    quotes = {'quotes': [{'symbol': f'{code}.US', 'lastDone': 100} for code in symbols]}

    async def _run() -> None:
        result, submit, _ = await _run_buy_cycle(
            signal=_ranked_buy_signals(*symbols),
            targets=[{'symbol': code, 'market': 'US'} for code in symbols],
            quote_result=quotes,
            custom_config={'max_symbols': 3},
            settings=_trade_settings(daily_buy_ratio=0.40),
        )
        submitted = [call.kwargs.get('symbol') for call in submit.call_args_list]
        assert submitted == ['AAPL', 'MSFT', 'NVDA']
        assert result['submittedOrdersCount'] == 3

    asyncio.run(_run())


def test_cycle_zero_nav_includes_broker_circuit_message() -> None:
    async def _run() -> None:
        result, submit, _ = await _run_buy_cycle(
            account_balance={
                'configured': True,
                'reason': 'circuit_open',
                'message': '长桥接口熔断中，稍后再试',
                'balances': [],
            },
        )
        submit.assert_not_called()
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '净资产为 0' in reasons
        assert '长桥接口熔断中' in reasons

    asyncio.run(_run())


def test_cycle_alpha_float_payload_does_not_raise() -> None:
    float_signal = {
        'signals': [
            {
                'symbol': 'AAPL',
                'market': 'US',
                'signal': 'BUY',
                'confidence': 88,
                'score': 88,
                'price': 100,
                'reason': 'ok',
                'factor_json': {'metrics': {'alpha101': 0.42, 'alpha158': 1.5, 'tradeDate': '2026-09-04'}},
            }
        ]
    }

    async def _run() -> None:
        result, submit, _ = await _run_buy_cycle(signal=float_signal)
        submit.assert_called_once()
        assert result['submittedOrdersCount'] == 1

    asyncio.run(_run())


def test_cycle_skips_buy_when_gross_exposure_exceeds_nav() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(
            positions=[{'symbol': 'MSFT.US', 'quantity': 50, 'marketValue': 12000}],
        )
        submit.assert_not_called()
        add_decision.assert_not_called()
        assert result['submittedOrdersCount'] == 0
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '总持仓' in reasons

    asyncio.run(_run())


def test_resolve_targets_drops_cn_and_uses_heat() -> None:
    async def _run() -> None:
        db = MagicMock()
        heat = SimpleNamespace(trade_date='2026-08-26')
        rows = [SimpleNamespace(symbol='NVDA', market='US')]
        watch = [SimpleNamespace(symbol='600519', market='CN'), SimpleNamespace(symbol='0700', market='HK')]
        with (
            patch('module_market.dao.heat_dao.MarketHeatDao.get_latest_heat', AsyncMock(side_effect=[heat, None])),
            patch('module_market.dao.heat_dao.MarketHeatDao.list_top50', AsyncMock(return_value=rows)),
            patch('module_market.dao.market_dao.MarketWatchlistDao.get_enabled', AsyncMock(return_value=watch)),
        ):
            items = await AutoTradeService._resolve_targets(db, None, user_id=1)
        markets = {item['market'] for item in items}
        symbols = {item['symbol'] for item in items}
        assert 'CN' not in markets
        assert 'NVDA' in symbols
        assert '0700' in symbols
        assert '600519' not in symbols

        dropped = await AutoTradeService._resolve_targets(
            db, [{'symbol': '600519', 'market': 'CN'}, {'symbol': 'AAPL', 'market': 'US'}]
        )
        assert dropped == [{'symbol': 'AAPL', 'market': 'US'}]

    asyncio.run(_run())


def test_cycle_skips_duplicate_buy_today() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(today_bought={'AAPL'})
        submit.assert_not_called()
        add_decision.assert_not_called()
        assert result['submittedOrdersCount'] == 0
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '今日已买入该标的' in reasons

    asyncio.run(_run())


def test_load_settings_defaults_symbol_pct_when_column_missing() -> None:
    from module_trade.service.auto_trade_service import AutoTradeService

    async def _run() -> None:
        db = MagicMock()
        row = SimpleNamespace(app_key='k', access_token='t', auto_trade_enabled='1', daily_buy_ratio=0.20)
        with patch('module_quant.dao.quant_dao.QuantLongbridgeConfigDao.get_config', AsyncMock(return_value=row)):
            settings = await AutoTradeService.load_user_trade_settings(db, 1)
        assert settings['max_symbol_position_pct'] == 0.10
        assert settings['has_keys'] is True
        assert settings['auto_trade_enabled'] is True
        assert settings['daily_buy_ratio'] == 0.20

    asyncio.run(_run())


def test_save_auto_trade_requires_keys() -> None:
    from exceptions.exception import ServiceException
    from module_trade.service.auto_trade_service import AutoTradeService

    async def _run() -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        with patch('module_quant.dao.quant_dao.QuantLongbridgeConfigDao.get_config', AsyncMock(return_value=None)):
            try:
                await AutoTradeService.save_user_trade_settings(db, 101, auto_trade_enabled=True)
            except ServiceException as exc:
                assert '未配置长桥账户 Key' in exc.message
                return
            raise AssertionError('expected ServiceException')

    asyncio.run(_run())


def test_realtime_price_map_prefers_hub_then_batches_rest() -> None:
    QuoteSubscribeHub.ingest_push(
        'AAPL.US', {'last_done': 190.5, 'prev_close': 180, 'timestamp': '2026-08-29 10:00:00'}
    )
    opps = [
        {'symbol': 'AAPL', 'market': 'US'},
        {'symbol': 'MSFT', 'market': 'US'},
        {'symbol': 'NVDA', 'market': 'US'},
    ]
    batch = {
        'quotes': [
            {'symbol': 'MSFT.US', 'lastDone': 420.0},
            {'symbol': 'NVDA.US', 'lastDone': 0},
        ]
    }

    async def _run() -> tuple[dict, dict]:
        with patch.object(LongbridgeService, 'get_realtime_quote', return_value=batch) as fetch:
            prices, errors = await AutoTradeService._realtime_price_map(opps)
            fetch.assert_called_once()
            assert fetch.call_args.args[0] == ['MSFT.US', 'NVDA.US']
        return prices, errors

    prices, errors = asyncio.run(_run())
    assert prices['AAPL'] == 190.5
    assert prices['MSFT'] == 420.0
    assert 'NVDA' not in prices
    assert errors == {}


def test_realtime_price_map_records_batch_failure_reason() -> None:
    opps = [{'symbol': 'AAPL', 'market': 'US'}]

    async def _run() -> tuple[dict, dict]:
        with patch.object(LongbridgeService, 'get_realtime_quote', side_effect=RuntimeError('quote down')):
            return await AutoTradeService._realtime_price_map(opps)

    prices, errors = asyncio.run(_run())
    assert prices == {}
    assert '获取实时报价失败' in errors['AAPL']
    assert 'quote down' in errors['AAPL']


def test_cycle_skips_when_realtime_quote_missing() -> None:
    async def _run() -> None:
        result, submit, add_decision = await _run_buy_cycle(quote_result={'quotes': []})
        submit.assert_not_called()
        add_decision.assert_not_called()
        assert result['submittedOrdersCount'] == 0
        reasons = ' '.join(item.get('reason') or '' for item in result['skippedReasons'])
        assert '未能获取券商有效盘中实时报价' in reasons

    asyncio.run(_run())
