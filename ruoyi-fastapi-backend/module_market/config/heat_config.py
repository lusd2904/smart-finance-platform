"""
市场热度看板配置：指数映射、市值过滤区间、默认权重。

权重可通过 sys_config 覆盖（键 market.heat.weight.*），未配置时使用下列默认值。
"""

from __future__ import annotations

from typing import Any

DEFAULT_HEAT_WEIGHTS: dict[str, float] = {
    'index': 0.4,
    'turnover': 0.3,
    'advance_decline': 0.3,
}

WEIGHT_CONFIG_KEYS: dict[str, str] = {
    'market.heat.weight.index': 'index',
    'market.heat.weight.turnover': 'turnover',
    'market.heat.weight.advance_decline': 'advance_decline',
}

MARKET_META: dict[str, dict[str, Any]] = {
    'US': {
        'label': '美股',
        'currency': 'USD',
        'index_symbol': '^GSPC',
        'index_name': '标普500',
        'cap_min': 1e9,
        'cap_max': 100e9,
        'cap_rule': '10亿-1000亿美元',
        'timezone': 'America/New_York',
        'close_hour_local': 16,
    },
    'HK': {
        'label': '港股',
        'currency': 'HKD',
        'index_symbol': 'HSI.HK',
        'index_name': '恒生指数',
        'cap_min': 10e9,
        'cap_max': 100e9,
        'cap_rule': '100亿-1000亿港币',
        'timezone': 'Asia/Hong_Kong',
        'close_hour_local': 16,
    },
    'CN': {
        'label': 'A股',
        'currency': 'CNY',
        'index_symbol': '000001',
        'index_name': '上证指数',
        'cap_min': 10e9,
        'cap_max': 200e9,
        'cap_rule': '100亿-2000亿人民币',
        'timezone': 'Asia/Shanghai',
        'close_hour_local': 15,
    },
}

VALID_MARKETS = frozenset(MARKET_META.keys())
