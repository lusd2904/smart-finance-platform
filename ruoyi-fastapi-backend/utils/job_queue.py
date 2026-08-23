"""
Redis 列表队列：把长任务从 API worker 卸到独立 jobs 消费组。

三组队列（同一套代码，不复制后端）：
- market：行情同步 / 简报 / 看板预热 / 内容缓存
- quant：因子 / 策略 / 止损 / 指标快照
- llm：舆情采集分析 / 自选研判 / 日评 / 需求沟通 summarize 与群聊回复

调度任务优先入队；HTTP 重操作只入队并立即返回 jobId。
"""

from __future__ import annotations

import asyncio
import json
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
}
KNOWN_JOBS = frozenset(JOB_GROUPS)


def group_for(job_type: str) -> str:
    return JOB_GROUPS.get(str(job_type or '').strip(), 'market')


def queue_key_for(job_type: str) -> str:
    return QUEUE_KEYS[group_for(job_type)]


class JobQueue:
    @classmethod
    def _redis(cls):
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
        keys = cls.consume_keys(group)
        logger.info(f'[job-queue] worker 已启动 group={group or "all"} keys={keys}')
        while not stop_event.is_set():
            if not keys:
                await asyncio.sleep(1)
                continue
            redis = cls._redis()
            if redis is None:
                await asyncio.sleep(1)
                continue
            try:
                item = await redis.brpop(keys, timeout=2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f'[job-queue] brpop 失败: {exc}')
                await asyncio.sleep(1)
                continue
            if not item:
                continue
            _key, raw = item
            job = cls.decode(raw)
            if not job:
                logger.warning('[job-queue] 丢弃无法解析的任务')
                continue
            job_type = str(job.get('type') or '')
            job_id = str(job.get('jobId') or '')
            try:
                await cls.mark_running(job_type)
                await cls._write_ticket(job, 'running')
                result = await cls.dispatch(job)
                await cls._write_ticket(job, 'done', result=result)
                logger.info(f'[job-queue] {job_type} 完成: {str(result)[:240]}')
            except Exception as exc:
                await cls._write_ticket(job, 'failed', error=str(exc))
                logger.error(f'[job-queue] {job_type} 失败: {exc}')
            finally:
                await cls.clear_running(job_type)
                if job_id:
                    await asyncio.sleep(0)
        logger.info('[job-queue] worker 已停止')

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
            except Exception:
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
    from config.database import AsyncSessionLocal
    from module_quant.entity.vo.quant_vo import RunStrategyModel
    from module_quant.service.quant_service import QuantService

    profile = str(payload.get('profile') or 'balanced')
    symbols = payload.get('symbols')
    async with AsyncSessionLocal() as db:
        return await QuantService.run_strategy_services(db, RunStrategyModel(profile=profile, symbols=symbols))


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
    from config.database import AsyncSessionLocal
    from module_quant.service.daily_list_service import DailyListService

    profile = str((payload or {}).get('profile') or 'balanced')
    user_id = int((payload or {}).get('userId') or 0)
    async with AsyncSessionLocal() as db:
        if user_id:
            return await DailyListService.scan_user(db, user_id, profile)
        return await DailyListService.scan_all_users(db, profile)


async def _daily_list_open(payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_quant.service.daily_list_service import DailyListService

    async with AsyncSessionLocal() as db:
        return await DailyListService.execute_queued(db)


async def _feishu_push(_payload: dict[str, Any]) -> dict[str, Any]:
    from config.database import AsyncSessionLocal
    from module_trade.service.feishu_push_service import FeishuPushService

    async with AsyncSessionLocal() as db:
        return await FeishuPushService.run_due(db)


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
}
