"""行情 WebSocket：指数快照 + 可选个股订阅。

端点：WS /ws/market/quotes?interval=15
- 鉴权：Cookie Admin-Token，或开帧 {type:auth,token}。不再接受 query token。
  JWT 签名 + Redis 会话一致；失败以 code=4401 关闭。
- 默认推送：每 interval 秒推送盘中指数快照，载荷与 GET /market/index/quotes 的 data 一致。
- 订阅：{type:subscribe,symbols:[{symbol,market}|'AAPL:US']} 后额外推 channel=quotes
  （quotes 字段，不用 data.items，避免旧客户端把个股当成指数）。
  盘中个股走长桥 QuoteContext.subscribe 推送缓存，腾讯补缺口；有推送时提前唤醒 quotes 通道。
- 心跳：'ping' 回 'pong'。
- 网关需为 /docker-api/ws/ 开启 Upgrade 头透传。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Annotated, Any

from fastapi import WebSocket, WebSocketDisconnect

from common.router import APIRouterPro
from module_market.service.index_quotes_service import MarketIndexService
from module_market.service.live_quotes_service import LiveQuotesService, parse_subscribe_symbols
from module_market.service.quote_subscribe_hub import QuoteSubscribeHub
from utils.log_util import logger
from utils.ws_auth import authorize_websocket, token_from_auth_frame, token_from_websocket, verify_token

market_ws_controller = APIRouterPro(prefix='/ws', order_num=98, tags=['行情实时通道'])
_token_from_auth_frame = token_from_auth_frame
_token_from_websocket = token_from_websocket
__all__ = [
    '_token_from_auth_frame',
    '_token_from_websocket',
    'market_ws_controller',
    'normalize_interval',
    'verify_token',
]

MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 60


def normalize_interval(raw: str | None) -> int:
    """钳制推送间隔到 [3, 60] 秒；非法输入取默认 15。"""
    try:
        value = int(raw) if raw else 15
    except (TypeError, ValueError):
        return 15
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


async def _index_snapshot() -> dict[str, Any]:
    data = await MarketIndexService.get_in_session_quotes()
    return {'code': 200, 'msg': '操作成功', 'channel': 'index', 'data': data}


async def _quotes_snapshot(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    data = await LiveQuotesService.get_quotes(pairs)
    return {'code': 200, 'msg': '操作成功', 'channel': 'quotes', 'quotes': data}


def parse_client_frame(raw: str) -> tuple[str, Any]:
    """解析客户端文本：ping / auth / subscribe / unsubscribe / other。"""
    if raw == 'ping':
        return 'ping', None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 'other', None
    if not isinstance(data, dict):
        return 'other', None
    kind = str(data.get('type') or '').strip().lower()
    if kind == 'auth':
        return 'auth', data.get('token')
    if kind == 'subscribe':
        return 'subscribe', parse_subscribe_symbols(data.get('symbols'))
    if kind == 'unsubscribe':
        if data.get('symbols'):
            return 'unsubscribe', parse_subscribe_symbols(data.get('symbols'))
        return 'unsubscribe', []
    return 'other', None


async def _apply_subscribe(
    websocket: WebSocket,
    subscribed: list[tuple[str, str]],
    pairs: list[tuple[str, str]],
    watcher_id: str,
    on_update: Any,
) -> None:
    subscribed.clear()
    subscribed.extend(pairs)
    await QuoteSubscribeHub.watch(watcher_id, pairs, on_update=on_update)
    if subscribed:
        await websocket.send_json(await _quotes_snapshot(subscribed))


async def _handle_client_message(
    websocket: WebSocket,
    message: str,
    subscribed: list[tuple[str, str]],
    watcher_id: str,
    on_update: Any,
) -> None:
    kind, payload = parse_client_frame(message)
    if kind == 'ping':
        await websocket.send_text('pong')
    elif kind == 'subscribe':
        await _apply_subscribe(websocket, subscribed, payload or [], watcher_id, on_update)
    elif kind == 'unsubscribe':
        if payload:
            drop = set(payload)
            subscribed[:] = [item for item in subscribed if item not in drop]
        else:
            subscribed.clear()
        await QuoteSubscribeHub.watch(watcher_id, subscribed, on_update=on_update)


async def _wait_interval(
    websocket: WebSocket,
    seconds: int,
    subscribed: list[tuple[str, str]],
    watcher_id: str,
    quote_event: asyncio.Event | None,
    on_update: Any,
) -> str:
    remaining = float(seconds)
    while remaining > 0:
        if quote_event is not None and quote_event.is_set():
            quote_event.clear()
            return 'quote'
        started = time.monotonic()
        receive_task = asyncio.create_task(websocket.receive_text())
        event_task = asyncio.create_task(quote_event.wait()) if quote_event is not None else None
        wait_set: set[asyncio.Task[Any]] = {receive_task}
        if event_task is not None:
            wait_set.add(event_task)
        done, pending = await asyncio.wait(wait_set, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if receive_task in done:
            message = receive_task.result()
            await _handle_client_message(websocket, message, subscribed, watcher_id, on_update)
            remaining -= time.monotonic() - started
            continue
        if event_task is not None and event_task in done:
            if quote_event is not None:
                quote_event.clear()
            return 'quote'
        return 'interval'
    return 'interval'


async def _authorize_websocket(websocket: WebSocket, query_token: str | None) -> bool:
    return await authorize_websocket(websocket, query_token)


@market_ws_controller.websocket('/market/quotes')
async def market_quotes_stream(
    websocket: WebSocket,
    token: Annotated[str | None, None] = None,
    interval: Annotated[str | None, None] = None,
) -> None:
    await websocket.accept()
    if not await _authorize_websocket(websocket, token):
        await websocket.close(code=4401, reason='未授权')
        return
    push_interval = normalize_interval(interval)
    subscribed: list[tuple[str, str]] = []
    watcher_id = f'ws:{id(websocket)}'
    loop = asyncio.get_running_loop()
    quote_event = asyncio.Event()

    def _notify() -> None:
        loop.call_soon_threadsafe(quote_event.set)

    logger.info(f'[行情WS] 连接建立 interval={push_interval}s')
    reason = 'interval'
    try:
        while True:
            if reason == 'interval':
                await websocket.send_json(await _index_snapshot())
            if subscribed:
                await websocket.send_json(await _quotes_snapshot(subscribed))
            reason = await _wait_interval(
                websocket, push_interval, subscribed, watcher_id, quote_event, _notify
            )
    except WebSocketDisconnect:
        logger.info('[行情WS] 客户端断开')
    except Exception as exc:
        logger.info(f'[行情WS] 连接结束: {exc}')
    finally:
        await QuoteSubscribeHub.unwatch(watcher_id)
