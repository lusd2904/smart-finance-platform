"""长桥 SDK 异常统一处置。

约定：
- 会触达券商网络的调用点在捕获异常后必须调用 note_sdk_error 记入熔断器；
- 未触达网络（如本地配置读取、上下文构建前的校验失败）只记日志，不计入熔断。
"""

from __future__ import annotations

from utils.longbridge_breaker import LongbridgeBreaker


def note_sdk_error(exc: BaseException) -> None:
    """把一次 SDK 调用失败记入熔断器（不抛出）。"""
    LongbridgeBreaker.record_failure(exc)
