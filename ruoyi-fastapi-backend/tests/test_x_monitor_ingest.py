"""X监测器批量入库：令牌门禁、空批次、插入与按 url 幂等跳过。"""

import hashlib
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.get_db import get_db
from exceptions.handle import handle_exception
from module_sentiment.controller.sentiment_ingest_controller import (
    sentiment_ingest_controller,
    verify_x_monitor_ingest_token,
)
from module_sentiment.service.collector_service import _map_x_monitor_item, _normalize_topics
from module_sentiment.service.sentiment_service import SentimentService


INGEST_TOKEN = 'test-x-monitor-ingest-token'
INGEST_PATH = '/sentiment/ingest/x_monitor'


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(sentiment_ingest_controller)
    handle_exception(app)

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    return app


def test_normalize_topics_array_and_csv() -> None:
    assert _normalize_topics(['USEquity', ' Fed ', '']) == ['USEquity', 'Fed']
    assert _normalize_topics('SPX,QQQ/VIX，Macro') == ['SPX', 'QQQ', 'VIX', 'Macro']
    assert _normalize_topics(None) == []


def test_map_x_monitor_item_forces_source_and_hashes_url() -> None:
    url = 'https://x.com/user/status/123'
    mapped = _map_x_monitor_item(
        {
            'posted_at': '2026-09-04T10:00:00+08:00',
            'author': 'fed',
            'author_id': '99',
            'text': 'Rate cut chatter\nmore',
            'url': url,
            'topics': ['Fed', 'USEquity'],
            'source': 'client_spoof',
        }
    )
    assert mapped is not None
    assert mapped['source'] == 'x_monitor'
    assert mapped['title'] == 'Rate cut chatter'
    assert '@fed' in mapped['content']
    assert 'Fed' in mapped['content']
    assert mapped['url'] == url
    assert mapped['uniq_hash'] == hashlib.md5(url.encode()).hexdigest()
    assert isinstance(mapped['pub_time'], datetime)
    assert mapped['pub_time'].hour == 10


def test_map_x_monitor_item_skips_empty() -> None:
    assert _map_x_monitor_item({'text': '', 'url': ''}) is None
    assert _map_x_monitor_item('not-a-dict') is None


def test_bad_token_is_401_or_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('SFP_X_MONITOR_INGEST_TOKEN', INGEST_TOKEN)
    with pytest.raises(HTTPException) as missing:
        verify_x_monitor_ingest_token(None)
    assert missing.value.status_code in (401, 403)

    with pytest.raises(HTTPException) as empty:
        verify_x_monitor_ingest_token('  ')
    assert empty.value.status_code in (401, 403)

    with pytest.raises(HTTPException) as wrong:
        verify_x_monitor_ingest_token('not-the-token')
    assert wrong.value.status_code in (401, 403)

    client = TestClient(_app())
    no_header = client.post(INGEST_PATH, json={'items': []})
    assert no_header.status_code in (401, 403)

    bad = client.post(INGEST_PATH, json={'items': []}, headers={'X-Ingest-Token': 'wrong'})
    assert bad.status_code in (401, 403)


def test_unconfigured_token_is_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('SFP_X_MONITOR_INGEST_TOKEN', raising=False)
    with pytest.raises(HTTPException) as exc:
        verify_x_monitor_ingest_token(INGEST_TOKEN)
    assert exc.value.status_code in (401, 403)


@pytest.mark.asyncio
async def test_empty_items_returns_zeros() -> None:
    db = AsyncMock()
    result = await SentimentService.ingest_x_monitor_services(db, [])
    assert result == {'accepted': 0, 'inserted': 0, 'skipped': 0}
    db.commit.assert_awaited()
    db.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_insert_then_duplicate_skip() -> None:
    url = 'https://x.com/fed/status/555'
    item = {
        'posted_at': '2026-09-04 11:00:00',
        'author': 'fed',
        'text': 'Tariff headline',
        'url': url,
        'topics': 'Tariff,Trump',
        'source': 'ignored',
    }
    uniq = hashlib.md5(url.encode()).hexdigest()
    db = AsyncMock()

    with (
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.get_existing_hashes',
            new=AsyncMock(return_value=set()),
        ) as existing,
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.add_news_batch',
            new=AsyncMock(return_value=[]),
        ) as add_batch,
    ):
        first = await SentimentService.ingest_x_monitor_services(db, [item])
    assert first == {'accepted': 1, 'inserted': 1, 'skipped': 0}
    existing.assert_awaited()
    added = add_batch.await_args.args[1]
    assert len(added) == 1
    assert added[0]['source'] == 'x_monitor'
    assert added[0]['analyzed'] == '0'
    assert added[0]['uniq_hash'] == uniq
    assert added[0]['create_time'] is not None

    with (
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.get_existing_hashes',
            new=AsyncMock(return_value={uniq}),
        ),
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.add_news_batch',
            new=AsyncMock(return_value=[]),
        ) as add_again,
    ):
        second = await SentimentService.ingest_x_monitor_services(db, [item, item])
    assert second == {'accepted': 2, 'inserted': 0, 'skipped': 2}
    add_again.assert_not_called()


def test_http_empty_items_and_insert_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('SFP_X_MONITOR_INGEST_TOKEN', INGEST_TOKEN)
    client = TestClient(_app())
    headers = {'X-Ingest-Token': INGEST_TOKEN}

    empty = client.post(INGEST_PATH, json={'items': []}, headers=headers)
    assert empty.status_code == 200
    assert empty.json()['data'] == {'accepted': 0, 'inserted': 0, 'skipped': 0}

    item = {
        'posted_at': '2026-09-04T12:00:00+08:00',
        'author': 'macro',
        'text': 'VIX spike',
        'url': 'https://x.com/macro/status/9',
        'topics': ['VIX'],
        'source': 'not-x',
    }
    with patch.object(
        SentimentService,
        'ingest_x_monitor_services',
        new=AsyncMock(return_value={'accepted': 1, 'inserted': 1, 'skipped': 0}),
    ) as ingest:
        first = client.post(INGEST_PATH, json={'items': [item]}, headers=headers)
    assert first.status_code == 200
    assert first.json()['data'] == {'accepted': 1, 'inserted': 1, 'skipped': 0}
    payload = ingest.await_args.args[1]
    assert payload[0]['source'] == 'not-x'
    assert payload[0]['url'] == item['url']

    with patch.object(
        SentimentService,
        'ingest_x_monitor_services',
        new=AsyncMock(return_value={'accepted': 1, 'inserted': 0, 'skipped': 1}),
    ):
        again = client.post(INGEST_PATH, json={'items': [item]}, headers=headers)
    assert again.status_code == 200
    assert again.json()['data'] == {'accepted': 1, 'inserted': 0, 'skipped': 1}
