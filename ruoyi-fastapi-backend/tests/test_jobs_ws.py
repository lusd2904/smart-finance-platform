"""任务进度 WS：间隔钳制、鉴权失败、心跳快照推送。"""

import os
import sys
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.env import JwtConfig
from module_analysis.controller.analysis_ws_controller import (
    analysis_ws_controller,
    jobs_lite_snapshot,
    normalize_interval,
)


def test_normalize_interval():
    assert normalize_interval(None) == 5
    assert normalize_interval('abc') == 5
    assert normalize_interval('1') == 3
    assert normalize_interval('999') == 30
    assert normalize_interval('10') == 10


def _make_token(valid: bool) -> str:
    if not valid:
        return 'not-a-jwt'
    return jwt.encode(
        {'user_id': '1', 'session_id': 's', 'exp': 4102444800},
        JwtConfig.jwt_secret_key,
        algorithm=JwtConfig.jwt_algorithm,
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(analysis_ws_controller)
    return app


def _session_ok(token: str):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=token)
    return patch('utils.ws_auth.RedisUtil.get_client', return_value=redis)


def test_jobs_ws_rejects_bad_token():
    client = TestClient(_app())
    closed = False
    try:
        with client.websocket_connect('/ws/jobs?interval=3') as ws:
            ws.send_text('{"type":"auth","token":"bad"}')
            ws.receive_text()
    except Exception:
        closed = True
    assert closed


def test_jobs_ws_pushes_channel_jobs():
    token = _make_token(True)
    heartbeat = {
        'alive': True,
        'ts': '2026-08-29 10:00:00',
        'queueDepth': 2,
        'running': [{'type': 'market_sync', 'startedAt': '2026-08-29 09:59:00'}],
    }
    with (
        _session_ok(token),
        patch(
            'module_analysis.controller.analysis_ws_controller.SchedulerRuntime.read_heartbeat',
            new=AsyncMock(return_value=heartbeat),
        ),
    ):
        client = TestClient(_app())
        with client.websocket_connect('/ws/jobs?interval=3') as ws:
            ws.send_text(f'{{"type":"auth","token":"{token}"}}')
            first = ws.receive_json()
            assert first['code'] == 200
            assert first['channel'] == 'jobs'
            assert first['data']['queueDepth'] == 2
            assert first['data']['schedulerAlive'] is True
            assert first['data']['heartbeatAt'] == '2026-08-29 10:00:00'
            assert first['data']['running'][0]['type'] == 'market_sync'
            assert 'items' not in first['data']
            ws.send_text('ping')
            assert ws.receive_text() == 'pong'


def test_jobs_lite_snapshot_uses_queue_when_scheduler_dead():
    async def _run() -> dict:
        with (
            patch(
                'module_analysis.controller.analysis_ws_controller.SchedulerRuntime.read_heartbeat',
                new=AsyncMock(return_value=None),
            ),
            patch(
                'module_analysis.controller.analysis_ws_controller.JobQueue.depth',
                new=AsyncMock(return_value=4),
            ),
        ):
            return await jobs_lite_snapshot()

    import asyncio

    payload = asyncio.run(_run())
    assert payload['channel'] == 'jobs'
    assert payload['data']['schedulerAlive'] is False
    assert payload['data']['queueDepth'] == 4
    assert payload['data']['running'] == []
    assert 'items' not in payload['data']
