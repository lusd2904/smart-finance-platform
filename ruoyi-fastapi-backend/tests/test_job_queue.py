import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from middlewares.audit_middleware import _should_skip
from utils.job_queue import HANDLERS, KNOWN_JOBS, JobQueue


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


@pytest.mark.asyncio
async def test_enqueue_without_redis_returns_false() -> None:
    assert await JobQueue.enqueue('market_sync', {'years': 1}) is False


def test_audit_skips_metrics_and_docs() -> None:
    assert _should_skip('/metrics')
    assert _should_skip('/docker-api/metrics')
    assert _should_skip('/docker-api/docs')
    assert not _should_skip('/market/watchlist/overview')
