import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_quant.service.factor_service import merge_profile_weights
from module_quant.service.longbridge_service import LongbridgeService
from module_quant.service.strategy_service import decide_signal


def test_merge_profile_weights_aliases_old_keys() -> None:
    weights = merge_profile_weights(
        'balanced',
        {'weights': {'volume': 0.4, 'value': 0.2, 'quality': 0.15, 'trend': 0.5}},
    )
    assert weights['volumeFlow'] == 0.4
    assert weights['reversion'] == 0.2
    assert weights['liquidity'] == 0.15
    assert weights['trend'] == 0.5


def test_decide_signal_reads_buy_threshold_alias() -> None:
    buy = decide_signal({'total': 60, 'riskLevel': 'low', 'trendDirection': 'up', 'tags': []}, 'balanced', {'buyThreshold': 50, 'sellThreshold': 20})
    assert buy['signal'] == 'BUY'


def test_list_strategy_profiles_prefers_user_overlay() -> None:
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch

    from module_trade.dao.trade_dao import TradeDao
    from module_trade.service.platform_ext_service import PlatformExtService

    default = SimpleNamespace(
        profile_code='balanced',
        profile_name='均衡',
        config_json='{"buyThreshold": 64}',
        update_time=None,
    )
    overlay = SimpleNamespace(
        profile_code='balanced',
        profile_name='均衡',
        config_json='{"buyThreshold": 70}',
        update_time=None,
    )

    async def _run() -> None:
        with (
            patch.object(PlatformExtService, 'ensure_seed_data', AsyncMock()),
            patch.object(TradeDao, 'list_strategy_profiles', AsyncMock(return_value=[default])),
            patch.object(TradeDao, 'list_user_strategy_profiles', AsyncMock(return_value=[overlay])),
            patch.object(TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=None)),
        ):
            rows = await PlatformExtService.list_strategy_profiles(MagicMock(), user_id=101)
        assert rows[0]['config']['buyThreshold'] == 70
        assert rows[0]['accountOwned'] is True
        assert rows[0]['active'] is True  # 未绑定时默认 balanced

        with (
            patch.object(PlatformExtService, 'ensure_seed_data', AsyncMock()),
            patch.object(TradeDao, 'get_user_strategy_profile', AsyncMock(return_value=overlay)),
        ):
            cfg = await PlatformExtService.get_profile_config(MagicMock(), 'balanced', user_id=101)
        assert cfg['buyThreshold'] == 70

    asyncio.run(_run())


def test_order_status_label() -> None:
    assert LongbridgeService._order_status_label('Filled') == '已成交'
    assert LongbridgeService._order_status_label('PartialFilled') == '部分成交'
    assert LongbridgeService._order_status_label('New') == '待成交'
