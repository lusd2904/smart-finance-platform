"""
Redis 列表队列：把长任务从 API worker 卸到独立 jobs 消费组。

三组队列（同一套代码，不复制后端）：
- market：行情同步 / 简报 / 看板预热 / 内容缓存
- quant：因子 / 策略 / 止损 / 指标快照
- llm：舆情采集分析 / 自选研判 / 日评 / 需求沟通 summarize 与群聊回复

调度任务优先入队；HTTP 重操作只入队并立即返回 jobId。

可靠队列语义：消费用 RPOPLPUSH 移入 sfp:job:processing:{group}（认领时间记于 sfp:job:claims），
成功 ACK 删除；失败按 JOB_MAX_RETRIES（默认3）重试，超限进 sfp:job:dead:{group} 死信；
崩溃遗留任务由消费循环按 JOB_VISIBILITY_TIMEOUT_S（默认900s）可见性超时定期回收。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Any

from common.constant import SchedulerConstant
from utils.log_util import logger

LEGACY_QUEUE_KEY = 'sfp:job:queue'
QUEUE_KEYS = {
    'market': 'sfp:job:queue:market',
    'quant': 'sfp:job:queue:quant',
    'llm': 'sfp:job:queue:llm',
}
CLAIMS_KEY = 'sfp:job:claims'
LEGACY_PROCESSING_KEY = 'sfp:job:processing'
LEGACY_DEAD_KEY = 'sfp:job:dead'
CONSUMER_POLL_SECONDS = 0.2
RECLAIM_INTERVAL_SECONDS = 30.0
_GROUP_BY_QUEUE = {v: k for k, v in QUEUE_KEYS.items()}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.environ.get(name) or '').strip())
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def visibility_timeout() -> int:
    """处理中任务可见性超时（秒），env JOB_VISIBILITY_TIMEOUT_S 可覆盖。"""
    return _env_int('JOB_VISIBILITY_TIMEOUT_S', 900)


def max_retries() -> int:
    """最大重试次数，超过即进死信列表，env JOB_MAX_RETRIES 可覆盖。"""
    return _env_int('JOB_MAX_RETRIES', 3)


def processing_key_for(queue_key: str) -> str:
    group = _GROUP_BY_QUEUE.get(queue_key)
    return f'sfp:job:processing:{group}' if group else LEGACY_PROCESSING_KEY


def dead_key_for(queue_key: str) -> str:
    group = _GROUP_BY_QUEUE.get(queue_key)
    return f'sfp:job:dead:{group}' if group else LEGACY_DEAD_KEY


TICKET_TTL_SECONDS = 3600
JOB_GROUPS = {
    'market_sync': 'market',
    'finance_briefings': 'market',
    'board_warmup': 'market',
    'symbol_content': 'market',
    'market_heat_collect': 'market',
    'factor_scan': 'quant',
    'factor_qc': 'quant',
    'indicator_refresh': 'quant',
    'strategy_run': 'quant',
    'position_monitor': 'quant',
    'sentiment_collect': 'llm',
    'sentiment_analyze': 'llm',
    'watchlist_analyze': 'llm',
    'daily_review': 'llm',
    'req_send': 'llm',
    'req_summarize': 'llm',
    'daily_list_scan': 'quant',
    'daily_list_open': 'quant',
    'feishu_push': 'llm',
    'stock_pick_run': 'llm',
    'eod_kline_sync': 'market',
    'market_review': 'llm',
}
KNOWN_JOBS = frozenset(JOB_GROUPS)


def group_for(job_type: str) -> str:
    return JOB_GROUPS.get(str(job_type or '').strip(), 'market')


def queue_key_for(job_type: str) -> str:
    return QUEUE_KEYS[group_for(job_type)]


class JobQueue:
    @classmethod
    def _redis(cls) -> Any:
        try:
            from config.get_redis import RedisUtil

            return RedisUtil.get_client()
        except Exception:
            return None

    @classmethod
    def encode(cls, job_type: str, payload: dict[str, Any] | None = None, job_id: str | None = None) -> str:
        job_type = str(job_type or '').strip()
        if job_type not in KNOWN_JOBS:
            raise ValueError(f'未知任务类型: {job_type}')
        return json.dumps(
            {
                'type': job_type,
                'payload': payload or {},
                'jobId': job_id or uuid.uuid4().hex,
                'queue': group_for(job_type),
                'enqueuedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            },
            ensure_ascii=False,
            default=str,
        )

    @classmethod
    def decode(cls, raw: Any) -> dict[str, Any] | None:
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            data = json.loads(raw)
        except Exception:
            return None
        if not isinstance(data, dict) or data.get('type') not in KNOWN_JOBS:
            return None
        return data

    @classmethod
    def ticket_view(cls, job: dict[str, Any], status: str = 'queued') -> dict[str, Any]:
        return {
            'accepted': True,
            'jobId': job.get('jobId'),
            'type': job.get('type'),
            'queue': job.get('queue') or group_for(str(job.get('type') or '')),
            'status': status,
            'enqueuedAt': job.get('enqueuedAt'),
        }

    @classmethod
    async def submit(cls, job_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        redis = cls._redis()
        if redis is None:
            return None
        job_id = uuid.uuid4().hex
        raw = cls.encode(job_type, payload, job_id=job_id)
        job = cls.decode(raw) or {}
        ticket = cls.ticket_view(job, 'queued')
        try:
            await redis.lpush(queue_key_for(job_type), raw)
            await redis.setex(cls._ticket_key(job_id), TICKET_TTL_SECONDS, json.dumps(ticket, ensure_ascii=False))
            return ticket
        except Exception as exc:
            logger.warning(f'[job-queue] 入队失败 {job_type}: {exc}')
            return None

    @classmethod
    async def enqueue(cls, job_type: str, payload: dict[str, Any] | None = None) -> bool:
        return bool(await cls.submit(job_type, payload))

    @classmethod
    async def get_ticket(cls, job_id: str) -> dict[str, Any] | None:
        redis = cls._redis()
        if redis is None or not job_id:
            return None
        try:
            raw = await redis.get(cls._ticket_key(job_id))
        except Exception:
            return None
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    @classmethod
    async def dispatch(cls, job: dict[str, Any]) -> Any:
        job_type = job.get('type')
        payload = job.get('payload') or {}
        handler = HANDLERS.get(job_type)
        if not handler:
            raise ValueError(f'无处理器: {job_type}')
        return await handler(payload)

    @classmethod
    def consume_keys(cls, group: str | None) -> list[str]:
        if not group or group in {'all', '*'}:
            return [LEGACY_QUEUE_KEY, *QUEUE_KEYS.values()]
        if group == 'none':
            return []
        key = QUEUE_KEYS.get(group)
        return [key] if key else []

    @classmethod
    async def consume_forever(cls, stop_event: asyncio.Event, group: str | None = None) -> None:
        """可靠队列消费循环：RPOPLPUSH 到处理中列表，成功 ACK，失败重试，超时回收，超限进死信。"""
        keys = cls.consume_keys(group)
        logger.info(f'[job-queue] worker 已启动 group={group or "all"} keys={keys}')
        next_reclaim = 0.0
        while not stop_event.is_set():
            if not keys:
                await asyncio.sleep(1)
                continue
            redis = cls._redis()
            if redis is None:
                await asyncio.sleep(1)
                continue
            try:
                if time.monotonic() >= next_reclaim:
                    next_reclaim = time.monotonic() + RECLAIM_INTERVAL_SECONDS
                    await cls.recover_stale(redis, keys)
                moved: tuple[str, Any] | None = None
                for key in keys:
                    raw = await redis.rpoplpush(key, processing_key_for(key))
                    if raw:
                        moved = (key, raw)
                        break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f'[job-queue] 消费取件失败: {exc}')
                await asyncio.sleep(1)
                continue
            if not moved:
                await asyncio.sleep(CONSUMER_POLL_SECONDS)
                continue
            src_key, raw = moved
            await cls._run_one(redis, src_key, raw)
        logger.info('[job-queue] worker 已停止')

    @classmethod
    async def _run_one(cls, redis: Any, src_key: str, raw: Any) -> None:
        proc_key = processing_key_for(src_key)
        job = cls.decode(raw)
        if not job:
            await cls._safe_lrem(redis, proc_key, raw)
            logger.warning('[job-queue] 丢弃无法解析的任务')
            return
        job_type = str(job.get('type') or '')
        job_id = str(job.get('jobId') or '')
        try:
            await cls._claim(redis, job_id)
            await cls.mark_running(job_type)
            await cls._write_ticket(job, 'running')
            result = await cls.dispatch(job)
            await cls._write_ticket(job, 'done', result=result)
            await cls._ack(redis, proc_key, raw, job_id)
            logger.info(f'[job-queue] {job_type} 完成: {str(result)[:240]}')
        except Exception as exc:
            await cls._write_ticket(job, 'failed', error=str(exc))
            logger.error(f'[job-queue] {job_type} 失败: {exc}')
            await cls._requeue_or_dead(redis, src_key, raw, job, str(exc))
        finally:
            await cls.clear_running(job_type)
            if job_id:
                await asyncio.sleep(0)

    @staticmethod
    async def _safe_lrem(redis: Any, key: str, value: Any) -> None:
        try:
            await redis.lrem(key, 1, value)
        except Exception as exc:
            logger.warning(f'[job-queue] LREM 失败 key={key}: {exc}')

    @classmethod
    async def _claim(cls, redis: Any, job_id: str) -> None:
        """记录认领时间戳；崩溃后由 recover_stale 按可见性超时回收。"""
        if not job_id:
            return
        try:
            await redis.hset(CLAIMS_KEY, job_id, time.time())
        except Exception as exc:
            logger.warning(f'[job-queue] 认领记录失败 job={job_id}: {exc}')

    @classmethod
    async def _ack(cls, redis: Any, proc_key: str, raw: Any, job_id: str) -> None:
        try:
            await cls._safe_lrem(redis, proc_key, raw)
            if job_id:
                await redis.hdel(CLAIMS_KEY, job_id)
        except Exception as exc:
            # ACK 失败时任务仍留在处理中列表，最终由可见性超时回收兜底
            logger.warning(f'[job-queue] ACK 异常 job={job_id}: {exc}')

    @classmethod
    async def _requeue_or_dead(cls, redis: Any, src_key: str, raw: Any, job: dict[str, Any], error: str) -> None:
        """从处理中列表移除后按重试计数决定重回主队列或进死信。"""
        proc_key = processing_key_for(src_key)
        job_id = str(job.get('jobId') or '')
        retries = int(job.get('retries') or 0)
        await cls._safe_lrem(redis, proc_key, raw)
        if job_id:
            try:
                await redis.hdel(CLAIMS_KEY, job_id)
            except Exception:
                pass
        next_retries = retries + 1
        if next_retries > max_retries():
            dead = {
                'job': job,
                'payload': job.get('payload') or {},
                'error': error[:500],
                'retries': retries,
                'failedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            try:
                await redis.lpush(dead_key_for(src_key), json.dumps(dead, ensure_ascii=False, default=str))
                logger.error(f'[job-queue] {job.get("type")} 重试超限进入死信 job={job_id} retries={retries}')
            except Exception as exc2:
                logger.warning(f'[job-queue] 死信写入失败 job={job_id}: {exc2}')
            return
        retried = dict(job)
        retried['retries'] = next_retries
        try:
            await redis.lpush(src_key, json.dumps(retried, ensure_ascii=False, default=str))
            logger.warning(
                f'[job-queue] {job.get("type")} 将重试({next_retries}/{max_retries()}) job={job_id}: {error[:200]}'
            )
        except Exception as exc2:
            logger.warning(f'[job-queue] 重试入队失败 job={job_id}: {exc2}')

    @classmethod
    async def recover_stale(cls, redis: Any, keys: list[str]) -> int:
        """扫描处理中列表：可见性超时的任务（进程崩溃遗留）回收回主队列或进死信。返回回收数量。"""
        timeout = visibility_timeout()
        try:
            now = time.time()
            claims = await redis.hgetall(CLAIMS_KEY)
        except Exception as exc:
            logger.warning(f'[job-queue] 回收扫描失败: {exc}')
            return 0
        claim_map: dict[str, float] = {}
        for field, ts in (claims or {}).items():
            name = field.decode('utf-8') if isinstance(field, bytes) else str(field)
            try:
                claim_map[name] = float(ts)
            except (TypeError, ValueError):
                continue
        recovered = 0
        for src_key in keys:
            proc_key = processing_key_for(src_key)
            try:
                entries = await redis.lrange(proc_key, 0, -1)
            except Exception:
                continue
            for entry in entries:
                job = cls.decode(entry)
                if not job:
                    continue
                job_id = str(job.get('jobId') or '')
                claimed_at = claim_map.get(job_id)
                if claimed_at is None:
                    # 无认领时间（旧版本遗留）：视为刚认领，避免误回收
                    try:
                        await redis.hset(CLAIMS_KEY, job_id, now)
                    except Exception:
                        pass
                    continue
                if now - claimed_at <= timeout:
                    continue
                recovered += 1
                await cls._requeue_or_dead(redis, src_key, entry, job, f'可见性超时回收（{timeout}s无响应）')
        return recovered

    @classmethod
    async def depth(cls, group: str | None = None) -> int:
        redis = cls._redis()
        if redis is None:
            return 0
        keys = cls.consume_keys(group) if group and group not in {'all', '*'} else [LEGACY_QUEUE_KEY, *QUEUE_KEYS.values()]
        total = 0
        for key in keys:
            try:
                total += int(await redis.llen(key) or 0)
            except Exception:  # noqa: PERF203 - 单队列 key 失败不中断其余统计
                continue
        return total

    @classmethod
    async def running_jobs(cls) -> list[dict[str, Any]]:
        redis = cls._redis()
        if redis is None:
            return []
        try:
            mapping = await redis.hgetall(SchedulerConstant.RUNNING_KEY)
        except Exception:
            return []
        items: list[dict[str, Any]] = []
        for key, started in (mapping or {}).items():
            name = key.decode('utf-8') if isinstance(key, bytes) else str(key)
            started_at = started.decode('utf-8') if isinstance(started, bytes) else str(started)
            items.append({'type': name, 'startedAt': started_at})
        return items

    @classmethod
    async def mark_running(cls, job_type: str) -> None:
        redis = cls._redis()
        if redis is None or not job_type:
            return
        try:
            await redis.hset(SchedulerConstant.RUNNING_KEY, job_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        except Exception:
            return

    @classmethod
    async def clear_running(cls, job_type: str) -> None:
        redis = cls._redis()
        if redis is None or not job_type:
            return
        try:
            await redis.hdel(SchedulerConstant.RUNNING_KEY, job_type)
        except Exception:
            return

    @classmethod
    def _ticket_key(cls, job_id: str) -> str:
        return f'sfp:job:ticket:{job_id}'

    @classmethod
    async def _write_ticket(cls, job: dict[str, Any], status: str, result: Any = None, error: str | None = None) -> None:
        job_id = str(job.get('jobId') or '')
        if not job_id:
            return
        redis = cls._redis()
        if redis is None:
            return
        ticket = cls.ticket_view(job, status)
        if result is not None:
            ticket['resultPreview'] = str(result)[:240]
        if error:
            ticket['error'] = error[:500]
        try:
            await redis.setex(cls._ticket_key(job_id), TICKET_TTL_SECONDS, json.dumps(ticket, ensure_ascii=False, default=str))
        except Exception:
            return


async def _market_sync(payload: dict[str, Any]) -> dict[str, Any]:
    from module_market.service.sync_service import MarketSyncService

    years = int(payload.get('years') or 10)
    symbol = payload.get('symbol')
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, MarketSyncService.sync, symbol, years)


async def _finance_briefings(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.finance_news_service import FinanceNewsService

    async with AsyncSessionLocal() as db:
        return await FinanceNewsService.refresh_all_markets(db)


async def _board_warmup(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.market_service import MarketService

    async with AsyncSessionLocal() as db:
        return await MarketService.refresh_board_quotes_cache(db)


async def _symbol_content(_payload: dict[str, Any]) -> dict[str, Any]:
    from module_task.market_task import refresh_symbol_content_now

    return await refresh_symbol_content_now()


async def _factor_scan(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.snapshot_service import SnapshotService

    profile = str(payload.get('profile') or 'balanced')
    async with AsyncSessionLocal() as db:
        return await SnapshotService.run_daily_factor_scan(db, profile=profile)


async def _factor_qc(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.factor_qc_service import FactorQcService

    market = str(payload.get('market') or 'US')
    async with AsyncSessionLocal() as db:
        return await FactorQcService.run_and_store(db, market=market)


async def _sentiment_collect(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_sentiment.service.sentiment_service import SentimentService

    async with AsyncSessionLocal() as db:
        if payload.get('analyze'):
            return await SentimentService.collect_and_analyze_services(db)
        return await SentimentService.collect_news_services(db)


async def _sentiment_analyze(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_sentiment.service.sentiment_service import SentimentService

    async with AsyncSessionLocal() as db:
        return await SentimentService.run_analysis_services(db)


async def _market_heat_collect(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.heat_service import MarketHeatService
    from utils.longbridge_breaker import LongbridgeBreaker

    market = str(payload.get('market') or 'US').upper()
    trade_date = payload.get('tradeDate')
    if not LongbridgeBreaker.allow():
        return {'skipped': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message(), 'market': market}
    async with AsyncSessionLocal() as db:
        return await MarketHeatService.collect_market(db, market=market, trade_date=trade_date)


async def _watchlist_analyze(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.watchlist_service import MarketWatchlistService
    from utils.longbridge_breaker import LongbridgeBreaker

    if not LongbridgeBreaker.allow():
        return {'skipped': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message()}
    async with AsyncSessionLocal() as db:
        return await MarketWatchlistService.run_hourly_job(db)


async def _indicator_refresh(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.snapshot_service import SnapshotService

    async with AsyncSessionLocal() as db:
        return await SnapshotService.run_indicator_refresh(db)


async def _strategy_run(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
    from module_quant.entity.vo.quant_vo import (  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
        RunStrategyModel,
    )
    from module_quant.service.quant_service import QuantService  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链

    profile = str(payload.get('profile') or 'balanced')
    symbols = payload.get('symbols')
    user_id = int(payload.get('userId') or 0) or None
    async with AsyncSessionLocal() as db:
        return await QuantService.run_strategy_services(
            db, RunStrategyModel(profile=profile, symbols=symbols), user_id=user_id
        )


async def _position_monitor(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.snapshot_service import SnapshotService
    from utils.longbridge_breaker import LongbridgeBreaker

    if not LongbridgeBreaker.allow():
        return {'skipped': True, 'reason': 'circuit_open', 'message': LongbridgeBreaker.blocked_message()}
    async with AsyncSessionLocal() as db:
        return await SnapshotService.run_position_monitor(db)


async def _daily_review(payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload or {})
    merged['analyze'] = True
    return await _sentiment_collect(merged)


async def _req_send(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_ai.service.ai_req_service import AiReqService

    async with AsyncSessionLocal() as db:
        return await AiReqService.process_send_job(db, payload or {})


async def _req_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_ai.service.ai_req_service import AiReqService

    async with AsyncSessionLocal() as db:
        return await AiReqService.process_summarize_job(db, payload or {})


async def _daily_list_scan(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
    from module_quant.service.daily_list_service import (  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
        DailyListService,
    )

    profile = str((payload or {}).get('profile') or 'balanced')
    user_id = int((payload or {}).get('userId') or 0)
    async with AsyncSessionLocal() as db:
        if user_id:
            return await DailyListService.scan_user(db, user_id, profile)
        return await DailyListService.scan_all_users(db, profile)


async def _daily_list_open(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
    from module_quant.service.daily_list_service import (  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
        DailyListService,
    )

    async with AsyncSessionLocal() as db:
        return await DailyListService.execute_queued(db)


async def _stock_pick_run(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal  # noqa: PLC0415
    from module_market.service.stock_pick_service import StockPickService  # noqa: PLC0415

    trigger = str((payload or {}).get('trigger') or 'schedule')
    use_ai = bool((payload or {}).get('useAi', True))
    async with AsyncSessionLocal() as db:
        return await StockPickService.run(db, trigger=trigger, use_ai=use_ai)


async def _eod_kline_sync(payload: dict[str, Any]) -> dict[str, Any]:
    from module_market.service.sync_service import MarketSyncService  # noqa: PLC0415

    market = str((payload or {}).get('market') or 'US').upper()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: MarketSyncService.sync_eod_market(market))


async def _feishu_push(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
    from module_trade.service.feishu_push_service import (  # noqa: PLC0415 - 队列 handler 延迟加载，缩短模块导入链
        FeishuPushService,
    )

    async with AsyncSessionLocal() as db:
        return await FeishuPushService.run_due(db)


async def _market_review(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_market.service.market_review_service import MarketReviewService

    markets = payload.get('markets')
    async with AsyncSessionLocal() as db:
        return await MarketReviewService.analyze_markets(db, markets)


HANDLERS = {
    'market_sync': _market_sync,
    'finance_briefings': _finance_briefings,
    'board_warmup': _board_warmup,
    'symbol_content': _symbol_content,
    'market_heat_collect': _market_heat_collect,
    'factor_scan': _factor_scan,
    'factor_qc': _factor_qc,
    'sentiment_collect': _sentiment_collect,
    'sentiment_analyze': _sentiment_analyze,
    'watchlist_analyze': _watchlist_analyze,
    'indicator_refresh': _indicator_refresh,
    'strategy_run': _strategy_run,
    'position_monitor': _position_monitor,
    'daily_review': _daily_review,
    'req_send': _req_send,
    'req_summarize': _req_summarize,
    'daily_list_scan': _daily_list_scan,
    'daily_list_open': _daily_list_open,
    'feishu_push': _feishu_push,
    'stock_pick_run': _stock_pick_run,
    'eod_kline_sync': _eod_kline_sync,
    'market_review': _market_review,
}
