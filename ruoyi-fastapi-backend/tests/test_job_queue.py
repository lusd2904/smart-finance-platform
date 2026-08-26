import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from middlewares.audit_middleware import _should_skip
from utils import job_queue as jq
from utils.job_queue import (
    CLAIMS_KEY,
    HANDLERS,
    JOB_GROUPS,
    KNOWN_JOBS,
    JobQueue,
    dead_key_for,
    group_for,
    processing_key_for,
)


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
    assert group_for('auto_trade_scan') == 'quant'
    assert group_for('watchlist_analyze') == 'llm'
    assert group_for('sentiment_analyze') == 'llm'
    assert group_for('req_send') == 'llm'
    assert group_for('req_summarize') == 'llm'
    assert group_for('stock_pick_run') == 'llm'
    assert group_for('eod_kline_sync') == 'market'
    assert JobQueue.consume_keys('none') == []
    assert 'sfp:job:queue:market' in JobQueue.consume_keys('market')
    assert 'sfp:job:queue:quant' in JobQueue.consume_keys('all')


def test_processing_and_dead_keys() -> None:
    assert processing_key_for('sfp:job:queue:quant') == 'sfp:job:processing:quant'
    assert dead_key_for('sfp:job:queue:market') == 'sfp:job:dead:market'
    # 遗留队列退化为不带组后缀的 key
    assert processing_key_for('sfp:job:queue') == 'sfp:job:processing'
    assert dead_key_for('sfp:job:queue') == 'sfp:job:dead'


@pytest.mark.asyncio
async def test_enqueue_without_redis_returns_false() -> None:
    assert await JobQueue.enqueue('market_sync', {'years': 1}) is False
    assert await JobQueue.enqueue('auto_trade_scan', {'profile': 'balanced'}) is False


@pytest.mark.asyncio
async def test_auto_trade_scan_job_enqueues(monkeypatch):
    from module_task.trade_task import run_auto_trade_scan_job

    captured: dict = {}

    async def fake_enqueue(job_type, payload=None):
        captured['type'] = job_type
        captured['payload'] = payload
        return True

    inline_called = {'value': False}

    async def fake_now(**kwargs):
        inline_called['value'] = True
        return kwargs

    monkeypatch.setattr(JobQueue, 'enqueue', fake_enqueue)
    monkeypatch.setattr('module_task.trade_task.run_auto_trade_scan_now', fake_now)
    await run_auto_trade_scan_job('aggressive', userId=7)
    assert captured['type'] == 'auto_trade_scan'
    assert captured['payload'] == {'profile': 'aggressive', 'userId': 7}
    assert inline_called['value'] is False


@pytest.mark.asyncio
async def test_auto_trade_scan_job_falls_back_inline(monkeypatch):
    from module_task.trade_task import run_auto_trade_scan_job

    async def fake_enqueue(job_type, payload=None):
        return False

    ran = {}

    async def fake_now(profile='balanced', user_id=None):
        ran['profile'] = profile
        ran['userId'] = user_id
        return {'profile': profile, 'userId': user_id}

    monkeypatch.setattr(JobQueue, 'enqueue', fake_enqueue)
    monkeypatch.setattr('module_task.trade_task.run_auto_trade_scan_now', fake_now)
    await run_auto_trade_scan_job(profile='balanced')
    assert ran == {'profile': 'balanced', 'userId': None}


@pytest.mark.asyncio
async def test_queue_depth_and_running_without_redis() -> None:
    assert await JobQueue.depth() == 0
    assert await JobQueue.running_jobs() == []


class FakeRedis:
    """最小异步 Redis 假实现，覆盖 job_queue 用到的命令。"""

    def __init__(self) -> None:
        self.lists: dict[str, list] = defaultdict(list)
        self.hashes: dict[str, dict] = defaultdict(dict)
        self.kv: dict[str, object] = {}

    async def lpush(self, key, value):
        self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def rpoplpush(self, src, dst):
        if not self.lists[src]:
            return None
        value = self.lists[src].pop()
        self.lists[dst].insert(0, value)
        return value

    async def lrem(self, key, count, value):
        kept, removed = [], 0
        for item in self.lists[key]:
            if removed < count and item == value:
                removed += 1
                continue
            kept.append(item)
        self.lists[key][:] = kept
        return removed

    async def lrange(self, key, start, stop):
        lst = self.lists[key]
        end = None if stop == -1 else stop + 1
        return list(lst[start:end])

    async def llen(self, key):
        return len(self.lists[key])

    async def hset(self, key, field, value):
        self.hashes[key][field] = value
        return 1

    async def hdel(self, key, *fields):
        removed = 0
        for field in fields:
            if self.hashes[key].pop(field, None) is not None:
                removed += 1
        return removed

    async def hgetall(self, key):
        return dict(self.hashes[key])

    async def setex(self, key, seconds, value):
        self.kv[key] = value
        return True

    async def get(self, key):
        return self.kv.get(key)


@pytest.fixture()
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(JobQueue, '_redis', classmethod(lambda cls: fake))
    return fake


async def _run_worker_until(fake, predicate, group='quant', timeout=5.0):
    """启动消费循环直到 predicate 成立，然后优雅停止。"""
    stop = asyncio.Event()
    task = asyncio.create_task(JobQueue.consume_forever(stop, group))
    try:
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() > deadline:
                raise AssertionError('等待条件超时')
            await asyncio.sleep(0.02)
    finally:
        stop.set()
        await task


QUEUE_KEY = 'sfp:job:queue:quant'


@pytest.mark.asyncio
async def test_submit_enqueues_and_writes_ticket(fake_redis):
    ticket = await JobQueue.submit('factor_scan', {'profile': 'balanced'})
    assert ticket and ticket['accepted'] is True and ticket['status'] == 'queued'
    assert len(fake_redis.lists[QUEUE_KEY]) == 1
    fetched = await JobQueue.get_ticket(ticket['jobId'])
    assert fetched and fetched['jobId'] == ticket['jobId']
    trade_ticket = await JobQueue.submit('auto_trade_scan', {'profile': 'balanced', 'userId': 3})
    assert trade_ticket and trade_ticket['queue'] == 'quant'
    assert len(fake_redis.lists[QUEUE_KEY]) == 2


@pytest.mark.asyncio
async def test_consume_success_acks_processing(fake_redis, monkeypatch):
    done = asyncio.Event()

    async def ok_handler(payload):
        assert payload['profile'] == 'balanced'
        done.set()
        return {'ok': True}

    monkeypatch.setitem(HANDLERS, 'factor_scan', ok_handler)
    ticket = await JobQueue.submit('factor_scan', {'profile': 'balanced'})
    proc_key = processing_key_for(QUEUE_KEY)

    await _run_worker_until(
        fake_redis,
        lambda: done.is_set() and len(fake_redis.lists[proc_key]) == 0 and len(fake_redis.lists[CLAIMS_KEY]) == 0,
    )

    # ACK 后处理中列表与认领表均清空
    assert len(fake_redis.lists[proc_key]) == 0
    assert len(fake_redis.lists[CLAIMS_KEY]) == 0
    assert len(fake_redis.lists[dead_key_for(QUEUE_KEY)]) == 0
    result = await JobQueue.get_ticket(ticket['jobId'])
    assert result and result['status'] == 'done' and result['resultPreview'] == str({'ok': True})


@pytest.mark.asyncio
async def test_failure_retries_then_dead_letter(fake_redis, monkeypatch):
    monkeypatch.setenv('JOB_MAX_RETRIES', '2')
    calls = []

    async def bad_handler(payload):
        calls.append(payload)
        raise RuntimeError('boom')

    monkeypatch.setitem(HANDLERS, 'factor_scan', bad_handler)
    await JobQueue.submit('factor_scan', {'profile': 'aggressive'})
    dead_key = dead_key_for(QUEUE_KEY)

    await _run_worker_until(fake_redis, lambda: len(fake_redis.lists[dead_key]) >= 1)

    # 初始执行 + 2 次重试 = 3 次执行后进死信
    assert len(calls) == 3
    assert len(fake_redis.lists[QUEUE_KEY]) == 0
    assert len(fake_redis.lists[processing_key_for(QUEUE_KEY)]) == 0
    dead_raw = fake_redis.lists[dead_key][0]
    dead = __import__('json').loads(dead_raw)
    assert dead['error'] == 'boom'
    assert dead['payload'] == {'profile': 'aggressive'}
    assert dead['retries'] == 2
    assert dead['failedAt']


@pytest.mark.asyncio
async def test_stale_claim_recovered_to_queue(fake_redis, monkeypatch):
    monkeypatch.setenv('JOB_VISIBILITY_TIMEOUT_S', '60')
    raw = JobQueue.encode('factor_scan', {'profile': 'balanced'})
    job = JobQueue.decode(raw)
    fake_redis.lists[processing_key_for(QUEUE_KEY)].append(raw)
    # 认领时间早已超时（模拟进程崩溃遗留）
    await fake_redis.hset(CLAIMS_KEY, job['jobId'], jq.time.time() - 3600)

    recovered = await JobQueue.recover_stale(fake_redis, [QUEUE_KEY])

    assert recovered == 1
    assert len(fake_redis.lists[processing_key_for(QUEUE_KEY)]) == 0
    assert len(fake_redis.lists[QUEUE_KEY]) == 1
    retried = JobQueue.decode(fake_redis.lists[QUEUE_KEY][0])
    assert retried['retries'] == 1
    assert fake_redis.hashes[CLAIMS_KEY] == {}


@pytest.mark.asyncio
async def test_stale_over_limit_goes_dead(fake_redis, monkeypatch):
    monkeypatch.setenv('JOB_VISIBILITY_TIMEOUT_S', '60')
    monkeypatch.setenv('JOB_MAX_RETRIES', '3')
    raw = JobQueue.encode('factor_scan', {'profile': 'balanced'})
    job = JobQueue.decode(raw)
    job['retries'] = 3
    stale_raw = __import__('json').dumps(job, ensure_ascii=False)
    fake_redis.lists[processing_key_for(QUEUE_KEY)].append(stale_raw)
    await fake_redis.hset(CLAIMS_KEY, job['jobId'], jq.time.time() - 3600)

    recovered = await JobQueue.recover_stale(fake_redis, [QUEUE_KEY])

    assert recovered == 1
    assert len(fake_redis.lists[QUEUE_KEY]) == 0
    dead = __import__('json').loads(fake_redis.lists[dead_key_for(QUEUE_KEY)][0])
    assert dead['error'].startswith('可见性超时')
    assert dead['retries'] == 3


@pytest.mark.asyncio
async def test_fresh_claim_not_reclaimed(fake_redis, monkeypatch):
    monkeypatch.setenv('JOB_VISIBILITY_TIMEOUT_S', '900')
    raw = JobQueue.encode('factor_scan', {})
    job = JobQueue.decode(raw)
    fake_redis.lists[processing_key_for(QUEUE_KEY)].append(raw)
    await fake_redis.hset(CLAIMS_KEY, job['jobId'], jq.time.time())

    assert await JobQueue.recover_stale(fake_redis, [QUEUE_KEY]) == 0
    assert len(fake_redis.lists[processing_key_for(QUEUE_KEY)]) == 1
    assert len(fake_redis.lists[QUEUE_KEY]) == 0


@pytest.mark.asyncio
async def test_unclaimed_legacy_entry_adopted_not_reclaimed(fake_redis, monkeypatch):
    """旧版本遗留的无认领记录任务：视为刚认领，不误回收。"""
    monkeypatch.setenv('JOB_VISIBILITY_TIMEOUT_S', '60')
    raw = JobQueue.encode('factor_scan', {})
    job = JobQueue.decode(raw)
    fake_redis.lists[processing_key_for(QUEUE_KEY)].append(raw)

    assert await JobQueue.recover_stale(fake_redis, [QUEUE_KEY]) == 0
    assert len(fake_redis.lists[QUEUE_KEY]) == 0
    assert float(fake_redis.hashes[CLAIMS_KEY][job['jobId']]) > 0


def test_audit_skips_metrics_and_docs() -> None:
    assert _should_skip('/metrics')
    assert _should_skip('/docker-api/metrics')
    assert _should_skip('/docker-api/docs')
    assert not _should_skip('/market/watchlist/overview')
