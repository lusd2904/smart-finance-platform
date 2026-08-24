"""行情指数 WebSocket 通道（规划文档「SSE/WebSocket 行情通道」开放项落地）。

端点：WS /ws/market/quotes?token=<JWT>&interval=5
- 鉴权：仅校验 JWT 签名与有效期（不查库/不查会话，读-only 行情足够）；
  失败以 code=4401 关闭连接。
- 推送：每 interval 秒推送一次盘中指数快照，载荷形态与
  GET /market/index/quotes 的 data 完全一致（客户端可复用解析）。
- 心跳：推送间隙监听客户端文本，'ping' 回 'pong'，其余忽略；
  等待超时即推送下一轮。
- 断开：任何发送异常即退出循环释放资源。

网关需为 /docker-api/ws/ 开启 Upgrade 头透传（见 nginx.dockersentiment.conf）。
"""

import asyncio
from typing import Annotated, Any

import jwt
from fastapi import WebSocket, WebSocketDisconnect

from common.router import APIRouterPro
from config.env import JwtConfig
from module_market.service.index_quotes_service import MarketIndexService
from utils.log_util import logger

market_ws_controller = APIRouterPro(prefix='/ws', order_num=98, tags=['行情实时通道'])

MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 60


def normalize_interval(raw: str | None) -> int:
    """钳制推送间隔到 [3, 60] 秒；非法输入取默认 5。"""
    try:
        value = int(raw) if raw else 5
    except (TypeError, ValueError):
        return 5
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


def verify_token(token: str | None) -> bool:
    """仅校验签名与有效期（exp），不做会话级校验。"""
    if not token:
        return False
    try:
        jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
        return True
    except Exception:  # noqa: BLE001 - 任何解码失败都视为未授权
        return False


async def _snapshot() -> dict[str, Any]:
    data = await MarketIndexService.get_in_session_quotes()
    return {'code': 200, 'msg': '操作成功', 'data': data}


@market_ws_controller.websocket('/market/quotes')
async def market_quotes_stream(
    websocket: WebSocket,
    token: Annotated[str | None, None] = None,
    interval: Annotated[str | None, None] = None,
) -> None:
    if not verify_token(token):
        await websocket.close(code=4401, reason='未授权')
        return

    await websocket.accept()
    push_interval = normalize_interval(interval)
    logger.info(f'[行情WS] 连接建立 interval={push_interval}s')
    try:
        while True:
            payload = await _snapshot()
            await websocket.send_json(payload)
            # 推送间隔内响应心跳；超时进入下一轮推送。
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=push_interval
                    )
                    if message == 'ping':
                        await websocket.send_text('pong')
                except asyncio.TimeoutError:
                    break
    except WebSocketDisconnect:
        logger.info('[行情WS] 客户端断开')
    except Exception as exc:  # noqa: BLE001 - 发送失败等统一按断开处理
        logger.info(f'[行情WS] 连接结束: {exc}')
