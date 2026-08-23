"""
长桥（Longbridge / longport）接入服务 —— 兼容 facade。

实现已拆分至 module_quant/service/longbridge/ 子包：
- auth.py         每用户凭据解析 / ContextVar 注入 / 全局限流
- region.py       区域归一化与接入端点
- errors.py       SDK 异常统一处置（熔断记录）
- quote_client.py 行情上下文与行情/盘口/K线/分时/资讯
- trade_client.py 交易上下文与账户/持仓/订单/下单撤单

本文件仅做全量再导出（含拆分前模块级公开符号），外部 import 路径保持不变。
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from contextvars import ContextVar
from typing import Any

from module_quant.service.longbridge import (
    ADMIN_LONGBRIDGE_USER_ID,
    LongbridgeService,
    peek_request_user_id,
    resolve_longbridge_user_id,
)
from module_quant.service.longbridge_quote import (
    CN_NO_DEPTH_MSG,
    assemble_depth,
    assemble_trades,
    empty_depth,
    empty_trades,
    is_cn_market,
    map_candlestick,
    map_intraday_point,
    overlay_last_bar,
    quote_error_message,
    quote_error_reason,
)
from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.longbridge_breaker import LongbridgeBreaker

__all__ = [
    'ADMIN_LONGBRIDGE_USER_ID',
    'CN_NO_DEPTH_MSG',
    'Any',
    'ContextVar',
    'LongbridgeBreaker',
    'LongbridgeService',
    'assemble_depth',
    'assemble_trades',
    'asyncio',
    'cache_get_json',
    'cache_set_json',
    'empty_depth',
    'empty_trades',
    'hashlib',
    'is_cn_market',
    'logger',
    'map_candlestick',
    'map_intraday_point',
    'os',
    'overlay_last_bar',
    'peek_request_user_id',
    'quote_error_message',
    'quote_error_reason',
    'resolve_longbridge_user_id',
    'time',
]
