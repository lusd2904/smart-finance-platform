"""下单/撤单入参服务端强校验契约测试。

背景：历史上 submit_order 对非法 side（如拼写错误 'byu'）静默映射为 Sell，
存在误卖风险；quantity<=0、空标的、限价单缺价格等均透传长桥 SDK 兜底。
本文件锁定：非法入参必须在服务端被显式拒绝，且绝不触发 SDK 调用。
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.longbridge import LongbridgeService

# ------------------------------------------------------- _validate_order_input ---


def test_market_order_needs_no_price() -> None:
    assert LongbridgeService._validate_order_input('AAPL.US', 'sell', 10, 'MO', None) is None


def test_valid_lo_order_passes() -> None:
    assert LongbridgeService._validate_order_input('AAPL.US', 'buy', 10, 'LO', 199.5) is None
    assert LongbridgeService._validate_order_input('00700.HK', 'SELL', 1, 'ELO', '320.4') is None
    assert LongbridgeService._validate_order_input('700', '买入', 100, 'AO', 0.5) is None
    assert LongbridgeService._validate_order_input('AAPL.US', ' BUY ', 10, 'LO', 1.0) is None


def test_invalid_side_rejected_not_mapped_to_sell() -> None:
    """核心回归：任何非白名单方向必须拒绝，禁止回退成卖出。"""
    for bad_side in ('byu', '', 'Buy.', '购买', 'null'):
        msg = LongbridgeService._validate_order_input('AAPL.US', bad_side, 10, 'LO', 1.0)
        assert msg is not None and '方向' in msg, f'side={bad_side!r} 应被拒绝'


def test_blank_symbol_rejected() -> None:
    msg = LongbridgeService._validate_order_input('  ', 'buy', 10, 'LO', 1.0)
    assert msg is not None and '标的代码' in msg


def test_quantity_must_be_positive_finite_number() -> None:
    for bad_qty in (0, -5, 'abc', None, float('nan'), float('inf')):
        msg = LongbridgeService._validate_order_input('AAPL.US', 'buy', bad_qty, 'LO', 1.0)
        assert msg is not None and '数量' in msg, f'quantity={bad_qty!r} 应被拒绝'


def test_unknown_order_type_rejected() -> None:
    msg = LongbridgeService._validate_order_input('AAPL.US', 'buy', 10, 'XX', 1.0)
    assert msg is not None and '订单类型' in msg


def test_limit_orders_require_positive_price() -> None:
    for ot in ('LO', 'ELO', 'AO'):
        for bad_price in (None, 0, -1, 'abc'):
            msg = LongbridgeService._validate_order_input('AAPL.US', 'buy', 10, ot, bad_price)
            assert msg is not None and '价格' in msg, f'{ot} price={bad_price!r} 应被拒绝'


# ------------------------------------------------------------ submit_order 级 ---


def _patch_ready() -> dict:
    """凭据齐全 + 实盘开关打开 + 可注入的 TradeContext。"""
    ctx = MagicMock()
    return {'ctx': ctx}


def test_submit_order_rejects_bad_side_without_sdk_call() -> None:
    ready = _patch_ready()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
    ):
        result = LongbridgeService.submit_order(
            symbol='AAPL.US', side='byu', quantity=10, order_type='LO', price=100.0, allow_sim=False
        )
    assert result['ok'] is False
    assert '方向' in result['message']
    ready['ctx'].submit_order.assert_not_called()


def test_submit_order_rejects_zero_quantity_without_sdk_call() -> None:
    ready = _patch_ready()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
    ):
        result = LongbridgeService.submit_order(
            symbol='AAPL.US', side='buy', quantity=0, order_type='LO', price=100.0, allow_sim=True
        )
    assert result['ok'] is False
    assert '数量' in result['message']
    ready['ctx'].submit_order.assert_not_called()


def test_submit_order_rejects_limit_order_without_price() -> None:
    ready = _patch_ready()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
    ):
        result = asyncio.run(
            LongbridgeService.submit_order_async(
                symbol='AAPL.US', side='buy', quantity=10, order_type='LO', price=None, allow_sim=True
            )
        )
    assert result['ok'] is False
    assert '价格' in result['message']
    ready['ctx'].submit_order.assert_not_called()


def test_us_submit_order_sets_anytime_outside_rth() -> None:
    from longport.openapi import OutsideRTH

    ready = _patch_ready()
    ready['ctx'].submit_order.return_value = type('R', (), {'order_id': 'ord-1'})()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
        patch(
            'module_market.service.index_session.us_outside_rth_mode',
            return_value='anytime',
        ),
    ):
        result = LongbridgeService.submit_order(
            symbol='AAPL',
            side='buy',
            quantity=1,
            order_type='LO',
            price=100.0,
            market='US',
            allow_sim=True,
        )
    assert result['ok'] is True
    assert result['outsideRth'] == 'anytime'
    kwargs = ready['ctx'].submit_order.call_args.kwargs
    assert kwargs['outside_rth'] == OutsideRTH.AnyTime
    assert kwargs['symbol'] == 'AAPL.US'


def test_us_submit_order_sets_overnight_outside_rth() -> None:
    from longport.openapi import OutsideRTH

    ready = _patch_ready()
    ready['ctx'].submit_order.return_value = type('R', (), {'order_id': 'ord-2'})()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
        patch(
            'module_market.service.index_session.us_outside_rth_mode',
            return_value='overnight',
        ),
    ):
        result = LongbridgeService.submit_order(
            symbol='NVDA.US',
            side='sell',
            quantity=2,
            order_type='MO',
            market='US',
            allow_sim=True,
        )
    assert result['ok'] is True
    assert result['outsideRth'] == 'overnight'
    kwargs = ready['ctx'].submit_order.call_args.kwargs
    assert kwargs['outside_rth'] == OutsideRTH.Overnight
    assert 'submitted_price' not in kwargs


def test_cn_submit_order_does_not_set_outside_rth() -> None:
    ready = _patch_ready()
    ready['ctx'].submit_order.return_value = type('R', (), {'order_id': 'ord-4'})()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
    ):
        result = LongbridgeService.submit_order(
            symbol='600519',
            side='buy',
            quantity=100,
            order_type='LO',
            price=1600.0,
            market='CN',
            allow_sim=True,
        )
    assert result['ok'] is True
    assert 'outside_rth' not in ready['ctx'].submit_order.call_args.kwargs


def test_build_config_enables_overnight_quotes() -> None:
    creds = {
        'app_key': 'k',
        'app_secret': 's',
        'access_token': 't',
        'region': 'hk',
        'user_id': '1',
        'source': 'db',
    }
    with (
        patch.object(LongbridgeService, 'resolve_credentials', return_value=creds),
        patch('longport.openapi.Config') as config_cls,
        patch('longport.openapi.Language'),
    ):
        config_cls.from_apikey.return_value = object()
        out = LongbridgeService._build_config()
    assert out is not None
    assert config_cls.from_apikey.call_args.kwargs.get('enable_overnight') is True


def test_hk_submit_order_does_not_set_outside_rth() -> None:
    ready = _patch_ready()
    ready['ctx'].submit_order.return_value = type('R', (), {'order_id': 'ord-3'})()
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
        patch.object(LongbridgeService, '_build_trade_context', return_value=ready['ctx']),
    ):
        result = LongbridgeService.submit_order(
            symbol='700',
            side='buy',
            quantity=100,
            order_type='LO',
            price=320.0,
            market='HK',
            allow_sim=True,
        )
    assert result['ok'] is True
    assert result.get('outsideRth') is None
    kwargs = ready['ctx'].submit_order.call_args.kwargs
    assert 'outside_rth' not in kwargs
    assert kwargs['symbol'] == '700.HK'


def test_cancel_order_requires_order_id() -> None:
    with (
        patch.object(LongbridgeService, 'is_configured', return_value=True),
        patch.object(LongbridgeService, 'is_trading_enabled', return_value=True),
    ):
        for blank in ('', '   ', None):
            result = LongbridgeService.cancel_order(blank, allow_sim=True)
            assert result['ok'] is False
            assert '订单号' in result['message']
