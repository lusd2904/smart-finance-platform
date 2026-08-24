"""长桥接入子包。

模块划分：
- auth.py         每用户凭据解析 / ContextVar 注入 / 全局限流与共享状态
- region.py       区域归一化与接入端点
- errors.py       SDK 异常统一处置（熔断记录）
- quote_client.py 行情上下文与行情/盘口/K线/分时/资讯
- trade_client.py 交易上下文与账户/持仓/订单/下单撤单

LongbridgeService 由三个 Mixin 组合而成，对外接口与拆分前完全一致；
原 module_quant/service/longbridge_service.py 仅作 facade 再导出。
"""

from __future__ import annotations

from module_quant.service.longbridge.auth import (
    ADMIN_LONGBRIDGE_USER_ID,
    CredentialsMixin,
    decrypt_or_raw,
    peek_request_user_id,
    resolve_longbridge_user_id,
)
from module_quant.service.longbridge.quote_client import QuoteClientMixin
from module_quant.service.longbridge.trade_client import TradeClientMixin

__all__ = [
    'ADMIN_LONGBRIDGE_USER_ID',
    'CredentialsMixin',
    'LongbridgeService',
    'QuoteClientMixin',
    'TradeClientMixin',
    'decrypt_or_raw',
    'peek_request_user_id',
    'resolve_longbridge_user_id',
]


class LongbridgeService(CredentialsMixin, QuoteClientMixin, TradeClientMixin):
    """
    长桥行情/交易封装。凭据缺失时所有方法返回 configured=False，不抛异常。
    """

