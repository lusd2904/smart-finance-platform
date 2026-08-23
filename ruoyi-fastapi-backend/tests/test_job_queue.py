import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from middlewares.audit_middleware import _should_skip
from utils.job_queue import HANDLERS, JOB_GROUPS, KNOWN_JOBS, JobQueue, group_for


def test_encode_decode_roundtrip() -> None:
    raw = JobQueue.encode('factor_scan', {'profile': 'balanced'})
    job = JobQueue.decode(raw)
    assert job is not None
    assert job['type'] == 'factor_scan'
    assert job['payload']['profile'] == 'balanced'
    assert 'enqueuedAt' in job


def test_unknown_job_rejected() -> None:
    with pytest.raises(ValueError):
        JobQueue.encode('not-a-job', {})
    assert JobQueue.decode('{"type":"nope"}') is None
    assert JobQueue.decode(b'not-json') is None


def test_handlers_cover_known_jobs() -> None:
    assert set(HANDLERS) == set(KNOWN_JOBS)
    assert set(JOB_GROUPS) == set(KNOWN_JOBS)
    assert group_for('market_sync') == 'market'
    assert group_for('board_warmup') == 'market'
    assert group_for('strategy_run') == 'quant'
    assert group_for('position_monitor') == 'quant'
    assert group_for('watchlist_analyze') == 'llm'
    assert group_for('sentiment_analyze') == 'llm'
    assert group_for('req_send') == 'llm'
    assert group_for('req_summarize') == 'llm'
    assert group_for('stock_pick_run') == 'llm'
    assert group_for('eod_kline_sync') == 'market'
    assert JobQueue.consume_keys('none') == []
    assert 'sfp:job:queue:market' in JobQueue.consume_keys('market')
    assert 'sfp:job:queue:quant' in JobQueue.consume_keys('all')


@pytest.mark.asyncio
async def test_enqueue_without_redis_returns_false() -> None:
    assert await JobQueue.enqueue('market_sync', {'years': 1}) is False


@pytest.mark.asyncio
async def test_queue_depth_and_running_without_redis() -> None:
    assert await JobQueue.depth() == 0
    assert await JobQueue.running_jobs() == []


def test_audit_skips_metrics_and_docs() -> None:
    assert _should_skip('/metrics')
    assert _should_skip('/docker-api/metrics')
    assert _should_skip('/docker-api/docs')
    assert not _should_skip('/market/watchlist/overview')
