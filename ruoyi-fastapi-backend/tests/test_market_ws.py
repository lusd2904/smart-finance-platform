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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.env import JwtConfig
from module_market.controller.market_ws_controller import (
    _token_from_websocket,
    market_ws_controller,
    normalize_interval,
    verify_token,
)
from utils.ws_auth import verify_ws_session


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


def _session_ok(token: str):
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=token)
    return patch('utils.ws_auth.RedisUtil.get_client', return_value=redis)


def test_ws_rejects_invalid_token():
    client = TestClient(_app())
    closed = False
    try:
        with client.websocket_connect('/ws/market/quotes?interval=3') as ws:
            ws.send_text('{"type":"auth","token":"bad"}')
            ws.receive_text()
    except Exception:
        closed = True
    assert closed


def test_ws_pushes_snapshot_and_pong():
    token = _make_token(True)
    fixture = {
        'items': [
            {
                'symbol': '.IXIC',
                'name': '纳斯达克',
                'market': 'US',
                'last': 20819.4,
                'changePct': 1.28,
                'quoteTime': '2026-08-24 10:00:00',
            },
        ],
        'asOf': '2026-08-24 10:00:00',
    }
    with (
        _session_ok(token),
        patch(
            'module_market.controller.market_ws_controller.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value=fixture),
        ),
    ):
        client = TestClient(_app())
        with client.websocket_connect('/ws/market/quotes?interval=3') as ws:
            ws.send_text(f'{{"type":"auth","token":"{token}"}}')
            first = ws.receive_json()
            assert first['code'] == 200
            assert first['data']['items'][0]['symbol'] == '.IXIC'
            # 心跳：ping → pong，随后仍能收到下一轮推送。
            ws.send_text('ping')
            assert ws.receive_text() == 'pong'
            second = ws.receive_json()
            assert second['data']['items'][0]['last'] == 20819.4


def test_token_from_auth_frame():
    from module_market.controller.market_ws_controller import _token_from_auth_frame

    assert _token_from_auth_frame('{"type":"auth","token":"abc"}') == 'abc'
    assert _token_from_auth_frame('ping') is None
    assert _token_from_auth_frame('{"type":"other"}') is None


def test_ws_accepts_first_frame_auth():
    token = _make_token(True)
    fixture = {
        'items': [{'symbol': '.IXIC', 'name': '纳斯达克', 'market': 'US', 'last': 1, 'changePct': 0}],
        'asOf': '2026-08-28 10:00:00',
    }
    with (
        _session_ok(token),
        patch(
            'module_market.controller.market_ws_controller.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value=fixture),
        ),
    ):
        client = TestClient(_app())
        with client.websocket_connect('/ws/market/quotes?interval=3') as ws:
            ws.send_text(f'{{"type":"auth","token":"{token}"}}')
            first = ws.receive_json()
            assert first['code'] == 200
            assert first['data']['items'][0]['symbol'] == '.IXIC'


def test_ws_subscribe_pushes_quotes_channel():
    token = _make_token(True)
    fixture = {
        'items': [{'symbol': '.IXIC', 'name': '纳斯达克', 'market': 'US', 'last': 1, 'changePct': 0}],
        'asOf': '2026-08-29 10:00:00',
    }
    live = {
        'items': [{'symbol': 'AAPL', 'market': 'US', 'last': 227.5, 'changePct': 0.5}],
        'asOf': '2026-08-29 10:00:00',
        'source': 'tencent',
    }
    with (
        _session_ok(token),
        patch(
            'module_market.controller.market_ws_controller.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value=fixture),
        ),
        patch(
            'module_market.controller.market_ws_controller.LiveQuotesService.get_quotes',
            new=AsyncMock(return_value=live),
        ),
    ):
        client = TestClient(_app())
        with client.websocket_connect('/ws/market/quotes?interval=3') as ws:
            ws.send_text(f'{{"type":"auth","token":"{token}"}}')
            first = ws.receive_json()
            assert first['data']['items'][0]['symbol'] == '.IXIC'
            assert first.get('channel') == 'index'
            ws.send_text('{"type":"subscribe","symbols":[{"symbol":"AAPL","market":"US"}]}')
            quotes = ws.receive_json()
            assert quotes['channel'] == 'quotes'
            assert 'data' not in quotes or not quotes.get('data')
            assert quotes['quotes']['items'][0]['symbol'] == 'AAPL'


def test_ws_token_prefers_cookie_over_query():
    ws = SimpleNamespace(cookies={'Admin-Token': 'cookie-token'})
    assert _token_from_websocket(ws, 'query-token') == 'cookie-token'
    empty = SimpleNamespace(cookies={})
    assert _token_from_websocket(empty, 'query-token') is None


def test_ws_ignores_query_token():
    client = TestClient(_app())
    closed = False
    try:
        with client.websocket_connect(f'/ws/market/quotes?token={_make_token(True)}&interval=3') as ws:
            ws.send_text('ping')
            ws.receive_text()
    except Exception:
        closed = True
    assert closed


def test_verify_token_shapes():
    assert verify_token(None) is False
    assert verify_token('') is False
    assert verify_token('garbage') is False
    assert verify_token(_make_token(True)) is True


def test_verify_ws_session_false_when_redis_mismatches():
    token = _make_token(True)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value='other-token')
    with patch('utils.ws_auth.RedisUtil.get_client', return_value=redis):
        assert asyncio.run(verify_ws_session(token)) is False


def test_verify_ws_session_false_when_redis_missing():
    token = _make_token(True)
    with patch('utils.ws_auth.RedisUtil.get_client', return_value=None):
        assert asyncio.run(verify_ws_session(token)) is False


def test_verify_ws_session_true_when_redis_matches():
    token = _make_token(True)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=token)
    with patch('utils.ws_auth.RedisUtil.get_client', return_value=redis):
        assert asyncio.run(verify_ws_session(token)) is True
    redis.get.assert_awaited()
    assert redis.get.await_args.args[0] == 'access_token:s'
