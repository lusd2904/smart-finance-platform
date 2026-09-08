"""Tests for internal job delegation endpoint used by Go market-worker."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from module_task.internal_jobs import router


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('INTERNAL_JOB_TOKEN', 'test-internal-token')
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.mark.asyncio
async def test_internal_job_requires_token(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        resp = await client.post('/internal/jobs/run', json={'type': 'market_heat_collect', 'payload': {'market': 'US'}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_internal_job_rejects_non_delegatable(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        resp = await client.post(
            '/internal/jobs/run',
            headers={'X-Internal-Token': 'test-internal-token'},
            json={'type': 'eod_kline_sync', 'payload': {'market': 'US'}},
        )
    assert resp.status_code == 400
    assert 'not delegatable' in resp.json()['detail']


@pytest.mark.asyncio
async def test_internal_job_runs_delegated_handler(app, monkeypatch):
    async def fake_heat(payload):
        return {'market': payload.get('market'), 'ok': True}

    monkeypatch.setitem(
        __import__('utils.job_queue', fromlist=['HANDLERS']).HANDLERS,
        'market_heat_collect',
        fake_heat,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        resp = await client.post(
            '/internal/jobs/run',
            headers={'X-Internal-Token': 'test-internal-token'},
            json={'type': 'market_heat_collect', 'payload': {'market': 'CN'}},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['result']['market'] == 'CN'


@pytest.mark.asyncio
async def test_strategy_evaluate_is_allowed_for_go_trade_jobs(app, monkeypatch):
    async def fake_eval(payload):
        return {'profile': payload.get('profile'), 'signals': [{'symbol': 'AAPL', 'signal': 'BUY'}]}

    monkeypatch.setattr('module_task.internal_jobs._strategy_evaluate', fake_eval)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        resp = await client.post(
            '/internal/jobs/run',
            headers={'X-Internal-Token': 'test-internal-token'},
            json={'type': 'strategy_evaluate', 'payload': {'profile': 'balanced', 'userId': 3}},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is True
    assert body['type'] == 'strategy_evaluate'
    assert body['result']['signals'][0]['symbol'] == 'AAPL'
