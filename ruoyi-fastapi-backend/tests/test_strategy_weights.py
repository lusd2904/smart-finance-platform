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


def test_order_status_label() -> None:
    assert LongbridgeService._order_status_label('Filled') == '已成交'
    assert LongbridgeService._order_status_label('PartialFilled') == '部分成交'
    assert LongbridgeService._order_status_label('New') == '待成交'
