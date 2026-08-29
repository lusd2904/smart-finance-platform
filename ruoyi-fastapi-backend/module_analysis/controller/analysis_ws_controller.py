"""任务进度 WebSocket：调度心跳 + 队列深度，不持有 DB。

端点：WS /ws/jobs?interval=5
- 鉴权：Cookie Admin-Token，或开帧 {type:auth,token}。JWT + Redis 会话一致。
- 推送：每 interval 秒推 Redis 心跳快照 {queueDepth, running, schedulerAlive, heartbeatAt}。
  不含 data.items，避免旧行情客户端把任务进度当成指数列表。
- 心跳：'ping' 回 'pong'。
- 网关需把 /docker-api/ws/jobs（及 /prod-api/ws/jobs）转到 platform，写在通用 /ws/ 之前。
"""

from __future__ import annotations

import asyncio
import time
from typing import Annotated, Any

from fastapi import WebSocket, WebSocketDisconnect

from common.router import APIRouterPro
from utils.job_queue import JobQueue
from utils.log_util import logger
from utils.scheduler_runtime import SchedulerRuntime
from utils.ws_auth import authorize_websocket

analysis_ws_controller = APIRouterPro(prefix='/ws', order_num=97, tags=['任务进度通道'])

MIN_INTERVAL_SECONDS = 3
MAX_INTERVAL_SECONDS = 30
DEFAULT_INTERVAL_SECONDS = 5


def normalize_interval(raw: str | None) -> int:
    """钳制推送间隔到 [3, 30] 秒；非法输入取默认 5。"""
    try:
        value = int(raw) if raw else DEFAULT_INTERVAL_SECONDS
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


async def jobs_lite_snapshot() -> dict[str, Any]:
    """Redis 心跳 + 队列深度，不查库、不含 jobs 清单。"""
    heartbeat = await SchedulerRuntime.read_heartbeat()
    alive = SchedulerRuntime.is_alive(heartbeat)
    running = (heartbeat or {}).get('running') if alive else []
    if not isinstance(running, list):
        running = []
    if alive:
        try:
            queue_depth = int((heartbeat or {}).get('queueDepth') or 0)
        except (TypeError, ValueError):
            queue_depth = 0
    else:
        queue_depth = await JobQueue.depth()
    return {
        'code': 200,
        'msg': '操作成功',
        'channel': 'jobs',
        'data': {
            'queueDepth': queue_depth,
            'running': running,
            'schedulerAlive': alive,
            'heartbeatAt': (heartbeat or {}).get('ts'),
        },
    }


async def _wait_interval(websocket: WebSocket, seconds: int) -> None:
    remaining = float(seconds)
    while remaining > 0:
        started = time.monotonic()
        try:
            message = await asyncio.wait_for(websocket.receive_text(), timeout=remaining)
        except asyncio.TimeoutError:
            return
        if message == 'ping':
            await websocket.send_text('pong')
        remaining -= time.monotonic() - started


@analysis_ws_controller.websocket('/jobs')
async def analysis_jobs_stream(
    websocket: WebSocket,
    token: Annotated[str | None, None] = None,
    interval: Annotated[str | None, None] = None,
) -> None:
    await websocket.accept()
    if not await authorize_websocket(websocket, token):
        await websocket.close(code=4401, reason='未授权')
        return
    push_interval = normalize_interval(interval)
    logger.info(f'[任务WS] 连接建立 interval={push_interval}s')
    try:
        while True:
            await websocket.send_json(await jobs_lite_snapshot())
            await _wait_interval(websocket, push_interval)
    except WebSocketDisconnect:
        logger.info('[任务WS] 客户端断开')
    except Exception as exc:
        logger.info(f'[任务WS] 连接结束: {exc}')
