import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_sentiment.service import collector_service as cs
from module_sentiment.service.collector_service import SentimentCollector


@pytest.mark.asyncio
async def test_fetch_x_monitor_reads_jsonl_and_dedupes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    jsonl = tmp_path / 'posts.jsonl'
    rows = [
        {
            'posted_at': '2026-09-04T10:00:00+08:00',
            'author': 'elonmusk',
            'author_id': '1',
            'text': 'First SpaceX update about Starship\nmore detail',
            'url': 'https://x.com/elonmusk/status/111',
            'topics': ['SpaceX', 'Musk'],
            'source': 'x_monitor',
        },
        {
            'posted_at': '2026-09-04 11:00:00',
            'author': 'xai',
            'author_id': '2',
            'text': 'Grok ships a new feature',
            'url': 'https://x.com/xai/status/222',
            'topics': 'Grok,Cursor',
            'source': 'x_monitor',
        },
        {
            'posted_at': '2026-09-04T12:00:00+08:00',
            'author': 'xai',
            'author_id': '2',
            'text': 'duplicate should vanish',
            'url': 'https://x.com/xai/status/222',
            'topics': ['Grok'],
            'source': 'x_monitor',
        },
        {
            'posted_at': '2026-09-04T13:00:00',
            'author': 'anon',
            'author_id': '3',
            'text': 'Mag7 chatter without url',
            'url': '',
            'topics': ['Mag7'],
            'source': 'x_monitor',
        },
    ]
    jsonl.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
    monkeypatch.setattr(cs, 'X_MONITOR_JSONL_PATH', jsonl)
    monkeypatch.setattr(cs, '_resolve_x_monitor_jsonl', lambda: jsonl)

    items = await SentimentCollector.fetch_x_monitor(None, page_size=200)
    assert len(items) == 3
    assert all(i['source'] == 'x_monitor' for i in items)
    assert [i['url'] for i in items if i['url']].count('https://x.com/xai/status/222') == 1
    assert items[0]['uniq_hash'] == cs._make_hash('x_monitor', 'Mag7 chatter without url')

    by_url = {i['url']: i for i in items if i['url']}
    first = by_url['https://x.com/elonmusk/status/111']
    assert first['title'] == 'First SpaceX update about Starship'
    assert 'SpaceX' in first['content']
    assert first['uniq_hash'] == hashlib.md5(b'https://x.com/elonmusk/status/111').hexdigest()
    assert isinstance(first['pub_time'], datetime)
    assert first['pub_time'].hour == 10

    out = await SentimentCollector.collect(['x_monitor'])
    assert len(out) == 3
    assert len({x['uniq_hash'] for x in out}) == 3


@pytest.mark.asyncio
async def test_fetch_x_monitor_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / 'nope.jsonl'
    monkeypatch.setattr(cs, 'X_MONITOR_JSONL_PATH', missing)
    monkeypatch.setattr(cs, '_resolve_x_monitor_jsonl', lambda: missing)
    assert await SentimentCollector.fetch_x_monitor(None) == []


def test_x_monitor_in_default_sources() -> None:
    assert 'x_monitor' in cs.DEFAULT_SOURCES
