"""
工作台聚合服务。

一次请求组装均衡总览所需的全部数据块；每个数据块独立降级，
任何一块失败都不影响其余块返回。整体结果写 Redis 短 TTL 缓存。
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any

from utils.json_cache import cache_get_json, cache_set_json
from utils.log_util import logger
from utils.time_format_util import format_beijing_datetime, now_beijing

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# 聚合结果缓存：按用户 + 权限指纹隔离，避免自选/权限块串号
SUMMARY_CACHE_TTL = 30
# 单块超时必须低于前端 axios 10s，避免一块拖垮整页（nginx 499）
SECTION_TIMEOUT_SEC = 5

# 交易时段近似边界（各市场本地时间，含午休简化处理）
_SESSION_START_HOUR = 9
_SESSION_END_HOUR = 16
_WEEKDAY_MAX = 4  # Monday=0 .. Friday=4

# 各数据块权限标识 → 响应字段；无权限的块直接返回 denied 空态
SECTION_PERMS: dict[str, str] = {
    'asset': 'quant:factor:list',
    'quotes': 'market:kline:list',
    'heat': 'market:heat:list',
    'watchSignals': 'market:watchlist:list',
    'sentiment': 'sentiment:news:list',
    'briefings': 'market:finance:list',
    'health': 'monitor:job:list',
}


def summary_cache_key(user_id: int | None, permissions: list[str] | None) -> str:
    """工作台缓存键：user_id + 权限集合哈希。"""
    uid = int(user_id or 0)
    perms = ','.join(sorted(str(p) for p in (permissions or []) if p))
    digest = hashlib.sha256(perms.encode('utf-8')).hexdigest()[:16]
    return f'dashboard:summary:{uid}:{digest}'


def _empty(section: str, reason: str = 'unavailable') -> dict[str, Any]:
    """数据块统一空态：前端据此渲染占位而非报错。"""
    return {'ok': False, 'reason': reason, 'data': None}


def _market_sessions() -> list[dict[str, Any]]:
    """三市场开闭市状态：按各时区本地时间判断工作日与收盘时段。"""
    from zoneinfo import ZoneInfo

    from module_market.config.heat_config import MARKET_META

    sessions = []
    for market in ('US', 'HK', 'CN'):
        meta = MARKET_META[market]
        now_local = datetime.now(ZoneInfo(meta['timezone']))
        is_weekday = now_local.weekday() <= _WEEKDAY_MAX
        hour = now_local.hour
        # 近似交易时段：US/HK/CN 统一 9:00-16:00 本地时间（午休简化处理）
        in_session = is_weekday and _SESSION_START_HOUR <= hour < _SESSION_END_HOUR
        sessions.append(
            {
                'market': market,
                'label': meta['label'],
                'timezone': meta['timezone'],
                'localDate': now_local.strftime('%Y-%m-%d'),
                'localTime': now_local.strftime('%H:%M'),
                'status': 'open' if in_session else ('closed' if is_weekday else 'weekend'),
            }
        )
    return sessions


class DashboardService:
    """工作台聚合：按权限裁剪数据块，逐块降级。"""

    @classmethod
    async def get_summary_services(
        cls, query_db: AsyncSession, user_id: int | None, permissions: list[str], use_cache: bool = True
    ) -> dict[str, Any]:
        """
        组装工作台总览。

        :param query_db: 会话
        :param user_id: 当前用户（自选信号按用户隔离；None 时跳过用户块）
        :param permissions: 当前用户权限列表，'*:*:*' 视为全部放行
        :param use_cache: 是否读取 30s 聚合缓存（refresh=true 时跳过并回写）
        :return: 聚合响应
        """
        cache_key = summary_cache_key(user_id, permissions)
        if use_cache:
            cached = await cache_get_json(cache_key)
            if isinstance(cached, dict) and cached.get('generatedAt'):
                return {**cached, 'cached': True}

        has = cls._make_perm_checker(permissions)
        sections = await cls._collect(query_db, user_id, has)

        summary = {
            'generatedAt': now_beijing().strftime('%Y-%m-%d %H:%M:%S'),
            'sessions': _market_sessions(),
            **sections,
        }
        await cache_set_json(cache_key, summary, SUMMARY_CACHE_TTL)
        return {**summary, 'cached': False}

    @classmethod
    def _make_perm_checker(cls, permissions: list[str]) -> Any:
        allowed = set(permissions or [])
        if '*:*:*' in allowed:

            def has(perm: str) -> bool:
                return True

        else:

            def has(perm: str) -> bool:
                return perm in allowed

        return has

    @classmethod
    async def _run_section(cls, section: str, coro: Any) -> dict[str, Any]:
        """单块限时执行：超时或异常都降级为空态，不拖垮整页。"""
        try:
            return await asyncio.wait_for(coro, timeout=SECTION_TIMEOUT_SEC)
        except TimeoutError:
            logger.warning(f'[工作台] 数据块 {section} 超时降级')
            return _empty(section, 'timeout')
        except Exception as exc:
            logger.warning(f'[工作台] 数据块 {section} 异常降级: {exc}')
            return _empty(section)

    @classmethod
    async def _collect(cls, query_db: AsyncSession, user_id: int | None, has: Any) -> dict[str, Any]:
        jobs: list[tuple[str, Any]] = [
            ('asset', cls._asset_block(query_db) if has(SECTION_PERMS['asset']) else cls._denied('asset')),
            ('quotes', cls._quotes_block(query_db) if has(SECTION_PERMS['quotes']) else cls._denied('quotes')),
            ('heat', cls._heat_block(query_db) if has(SECTION_PERMS['heat']) else cls._denied('heat')),
            (
                'watchSignals',
                (
                    cls._watch_signals_block(query_db, user_id)
                    if user_id and has(SECTION_PERMS['watchSignals'])
                    else cls._denied('watchSignals')
                ),
            ),
            (
                'sentiment',
                cls._sentiment_block(query_db) if has(SECTION_PERMS['sentiment']) else cls._denied('sentiment'),
            ),
            (
                'briefings',
                cls._briefings_block(query_db) if has(SECTION_PERMS['briefings']) else cls._denied('briefings'),
            ),
            ('health', cls._health_block(query_db) if has(SECTION_PERMS['health']) else cls._denied('health')),
        ]
        # AsyncSession 非并发安全：各块顺序执行。协程对象在列表里尚未调度。
        out: dict[str, Any] = {}
        for key, coro in jobs:
            out[key] = await cls._run_section(key, coro)
        return out

    @staticmethod
    async def _denied(section: str) -> dict[str, Any]:
        return _empty(section, 'denied')

    # ---------- 各数据块 ----------

    @staticmethod
    async def _asset_block(query_db: AsyncSession) -> dict[str, Any]:
        """账户资产：只读 scheduled overview，缺失时空态返回，绝不打长桥 live。"""
        from module_quant.service.readmodel_service import ReadModelService

        scheduled = await ReadModelService.get_scheduled('overview')
        asset = (scheduled or {}).get('asset') if isinstance(scheduled, dict) else None
        positions = (scheduled or {}).get('position') if isinstance(scheduled, dict) else None
        if not isinstance(asset, dict):
            return {
                'ok': True,
                'reason': None,
                'data': {
                    'configured': False,
                    'netAssets': None,
                    'availableCash': None,
                    'totalCash': None,
                    'currency': None,
                    'positionCount': positions.get('count') if isinstance(positions, dict) else 0,
                    'totalUnrealizedPnl': positions.get('totalUnrealizedPnl') if isinstance(positions, dict) else None,
                    'message': '读模型快照尚未生成',
                },
            }
        return {
            'ok': True,
            'reason': None,
            'data': {
                'configured': bool(asset.get('configured')),
                'netAssets': asset.get('netAssets'),
                'availableCash': asset.get('availableCash'),
                'totalCash': asset.get('totalCash'),
                'currency': asset.get('currency'),
                'positionCount': positions.get('count') if isinstance(positions, dict) else 0,
                'totalUnrealizedPnl': positions.get('totalUnrealizedPnl') if isinstance(positions, dict) else None,
                'message': asset.get('message') or None,
            },
        }

    @staticmethod
    async def _quotes_block(query_db: AsyncSession) -> dict[str, Any]:
        """指数/看板行情：只读 Redis 看板缓存，绝不打 Influx。"""
        from module_market.service.market_service import MarketService

        board = await MarketService.get_board_quotes_services(query_db)
        indices = board.get('indices') or []
        quotes = board.get('quotes') or []
        return {
            'ok': bool(indices or quotes),
            'reason': None if (indices or quotes) else (board.get('message') or '看板缓存尚未生成'),
            'data': {
                'indices': indices[:8],
                'quotes': quotes[:8],
                'source': board.get('source'),
                'stale': bool(board.get('stale')),
            },
        }

    @staticmethod
    async def _heat_block(query_db: AsyncSession) -> dict[str, Any]:
        """三市场最新热度摘要：指数涨跌 + 涨跌家数 + 成交额 + 热度分。"""
        from module_market.dao.heat_dao import MarketHeatDao
        from module_market.service.heat_service import MarketHeatService

        markets = {}
        for market in ('US', 'HK', 'CN'):
            row = await MarketHeatDao.get_latest_heat(query_db, market)
            if row is None:
                markets[market] = None
                continue
            heat = MarketHeatService._serialize_heat(row)
            markets[market] = {
                'tradeDate': heat.get('tradeDate'),
                'indexName': heat.get('indexName'),
                'indexChangePct': heat.get('indexChangePct'),
                'totalTurnover': heat.get('totalTurnover'),
                'advanceCount': heat.get('advanceCount'),
                'declineCount': heat.get('declineCount'),
                'flatCount': heat.get('flatCount'),
                'heatScore': heat.get('heatScore'),
                'asOfTime': heat.get('asOfTime'),
            }
        return {
            'ok': any(markets.values()),
            'reason': None if any(markets.values()) else '暂无热度快照，收盘任务完成后写入',
            'data': markets,
        }

    @staticmethod
    async def _watch_signals_block(query_db: AsyncSession, user_id: int | None) -> dict[str, Any]:
        """自选信号 Top5：按综合建议排序（偏多/偏空优先，中性靠后）。"""
        from module_market.service.watchlist_service import (
            MarketWatchlistService,
        )

        overview = await MarketWatchlistService.overview_services(query_db, user_id)
        items = overview.get('items') or []
        stance_rank = {'偏多': 0, '偏空': 1, '中性': 2}

        def _sort_key(item: dict[str, Any]) -> tuple[int, Any]:
            stance = item.get('stance') or ''
            rank = stance_rank.get(stance, 3)
            confidence = item.get('confidence')
            conf_val = confidence if isinstance(confidence, (int, float)) else -1
            return (rank, -conf_val)

        top = sorted(items, key=_sort_key)[:5]
        signals = [
            {
                'symbol': it.get('symbol'),
                'market': it.get('market'),
                'name': it.get('name'),
                'stance': it.get('stance'),
                'confidence': it.get('confidence'),
                'recommendation': it.get('recommendation'),
                'summary': (it.get('summary') or '')[:120],
                'last': it.get('last'),
                'changeRate': it.get('changeRate'),
                'analysisTime': it.get('analysisTime'),
            }
            for it in top
        ]
        return {
            'ok': bool(signals),
            'reason': None if signals else '暂无启用中的自选标的',
            'data': {
                'count': overview.get('count') or 0,
                'bullish': overview.get('bullish') or 0,
                'bearish': overview.get('bearish') or 0,
                'neutral': overview.get('neutral') or 0,
                'aiAvailable': overview.get('aiAvailable'),
                'signals': signals,
            },
        }

    @staticmethod
    async def _sentiment_block(query_db: AsyncSession) -> dict[str, Any]:
        """舆情统计 + 最新 AI 研判。"""
        from module_sentiment.dao.sentiment_dao import (
            SentimentAnalysisDao,
            SentimentNewsDao,
        )
        from module_sentiment.service.sentiment_service import SentimentService
        from utils.time_format_util import apply_beijing_times

        stats = await SentimentNewsDao.count_news(query_db)
        latest = await SentimentAnalysisDao.get_latest_analysis(query_db)
        latest_data = apply_beijing_times(SentimentService.dump_analysis_100(latest)) if latest else None
        return {
            'ok': True,
            'reason': None,
            'data': {
                'total': stats.get('total') or 0,
                'today': stats.get('today') or 0,
                'unanalyzed': stats.get('unanalyzed') or 0,
                'latestAnalysis': latest_data,
            },
        }

    @staticmethod
    async def _briefings_block(query_db: AsyncSession) -> dict[str, Any]:
        """财经简报流：只读库内已生成简报，不触发外部刷新。"""
        from module_market.dao.market_dao import FinanceBriefingDao

        rows = await FinanceBriefingDao.get_latest(query_db, limit=8)
        data = [
            {
                'market': r.market,
                'briefingType': r.briefing_type,
                'headline': r.headline,
                'summary': (r.summary or '')[:160],
                'sourceName': r.source_name,
                'sourceLink': r.source_link,
                'generatedAt': format_beijing_datetime(r.generated_at) if r.generated_at else None,
            }
            for r in rows
        ]
        return {
            'ok': bool(data),
            'reason': None if data else '简报尚未生成，采集任务完成后展示',
            'data': data,
        }

    @staticmethod
    async def _health_block(query_db: AsyncSession) -> dict[str, Any]:
        """运行状态：K线覆盖率 + 最近任务执行（成功/失败计数）。"""
        from datetime import timedelta

        from sqlalchemy import desc, func, select

        from module_admin.entity.do.job_do import SysJobLog
        from module_trade.service.platform_ext_service import (
            PlatformExtService,
        )

        since = datetime.now() - timedelta(hours=24)
        total = (
            await query_db.execute(select(func.count(SysJobLog.job_log_id)).where(SysJobLog.create_time >= since))
        ).scalar() or 0
        failed = (
            await query_db.execute(
                select(func.count(SysJobLog.job_log_id)).where(SysJobLog.create_time >= since, SysJobLog.status == '1')
            )
        ).scalar() or 0
        last_run = (
            (await query_db.execute(select(SysJobLog).order_by(desc(SysJobLog.create_time)).limit(1))).scalars().first()
        )

        coverage = None
        try:
            coverage = await PlatformExtService.history_coverage(query_db)
        except Exception as exc:  # 覆盖率失败不阻塞健康块
            logger.debug(f'[工作台] K线覆盖率查询失败: {exc}')

        return {
            'ok': True,
            'reason': None,
            'data': {
                'jobs24h': {'total': total, 'failed': failed},
                'lastJob': (
                    {
                        'jobName': last_run.job_name,
                        'status': last_run.status,
                        'createTime': format_beijing_datetime(last_run.create_time) if last_run.create_time else None,
                    }
                    if last_run
                    else None
                ),
                'coverage': (
                    {
                        'coveragePct': coverage.get('coveragePct'),
                        'covered': coverage.get('covered'),
                        'total': coverage.get('total'),
                        'missing': coverage.get('missing'),
                    }
                    if coverage
                    else None
                ),
            },
        }
