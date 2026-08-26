"""行情 WS 通道回归：间隔钳制、令牌校验、快照推送与心跳。"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import jwt
from config.env import JwtConfig
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module_market.controller.market_ws_controller import (
    market_ws_controller,
    normalize_interval,
    verify_token,
)


def test_normalize_interval():
    assert normalize_interval(None) == 15
    assert normalize_interval('abc') == 15
    assert normalize_interval('1') == 3  # 下限钳制
    assert normalize_interval('999') == 60  # 上限钳制
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
    app.include_router(market_ws_controller)
    return app


def test_ws_rejects_invalid_token():
    client = TestClient(_app())
    closed = False
    try:
        # 未授权时服务端在握手段即以 4401 关闭，异常发生在连接建立阶段。
        with client.websocket_connect('/ws/market/quotes?token=bad') as ws:
            ws.receive_text()
    except Exception:  # noqa: BLE001 - TestClient 对关闭帧抛 WebSocketDisconnect
        closed = True
    assert closed


def test_ws_pushes_snapshot_and_pong():
    fixture = {
        'items': [
            {'symbol': '.IXIC', 'name': '纳斯达克', 'market': 'US',
             'last': 20819.4, 'changePct': 1.28, 'quoteTime': '2026-08-24 10:00:00'},
        ],
        'asOf': '2026-08-24 10:00:00',
    }
    with patch(
        'module_market.controller.market_ws_controller.MarketIndexService.get_in_session_quotes',
        new=AsyncMock(return_value=fixture),
    ):
        client = TestClient(_app())
        with client.websocket_connect(
            f'/ws/market/quotes?token={_make_token(True)}&interval=3'
        ) as ws:
            first = ws.receive_json()
            assert first['code'] == 200
            assert first['data']['items'][0]['symbol'] == '.IXIC'
            # 心跳：ping → pong，随后仍能收到下一轮推送。
            ws.send_text('ping')
            assert ws.receive_text() == 'pong'
            second = ws.receive_json()
            assert second['data']['items'][0]['last'] == 20819.4


def test_verify_token_shapes():
    assert verify_token(None) is False
    assert verify_token('') is False
    assert verify_token('garbage') is False
    assert verify_token(_make_token(True)) is True
