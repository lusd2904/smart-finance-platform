from datetime import datetime
from typing import Any

from module_quant.service.longbridge_service import LongbridgeService
from utils.json_cache import cache_get_json, cache_set_json

_CACHE_TTL = 30
BOARD_TTL = 15 * 60
FACTOR_TTL = 6 * 3600
OVERVIEW_TTL = 6 * 3600
_MEMORY: dict[str, dict[str, Any]] = {}


def _memory_get(key: str) -> Any | None:
    entry = _MEMORY.get(key)
    if not entry:
        return None
    ts = entry.get('timestamp') or 0
    ttl = int(entry.get('ttl') or _CACHE_TTL)
    if (datetime.now().timestamp() - ts) >= ttl:
        return None
    return entry.get('data')


def _memory_set(key: str, data: Any, ttl: int = _CACHE_TTL) -> None:
    _MEMORY[key] = {'data': data, 'timestamp': datetime.now().timestamp(), 'ttl': ttl}


class ReadModelService:
    """
    读模型快照：定时快照优先，未命中再走 live（Redis + 进程内短缓存）。
    """

    @classmethod
    async def _get(cls, key: str) -> Any | None:
        cached = await cache_get_json(key)
        if cached is not None:
            return cached
        return _memory_get(key)

    @classmethod
    async def _set(cls, key: str, data: Any, ttl: int = _CACHE_TTL) -> None:
        _memory_set(key, data, ttl)
        await cache_set_json(key, data, ttl)

    @classmethod
    async def put_scheduled(cls, kind: str, data: Any, ttl: int) -> None:
        await cls._set(f'readmodel:scheduled:{kind}', data, ttl)

    @classmethod
    async def get_scheduled(cls, kind: str) -> Any | None:
        cached = await cls._get(f'readmodel:scheduled:{kind}')
        return cached if isinstance(cached, dict) else None

    @classmethod
    async def get_account_asset_snapshot(cls, use_scheduled: bool = True) -> dict[str, Any]:
        if use_scheduled:
            scheduled = await cls.get_scheduled('overview')
            if scheduled and isinstance(scheduled.get('asset'), dict):
                return scheduled['asset']
        cache_key = 'readmodel:account_asset'
        cached = await cls._get(cache_key)
        if cached:
            return cached

        acc = LongbridgeService.flatten_account(await LongbridgeService.get_account_balance_async())
        configured = bool(acc.get('configured'))
        snapshot = {
            'configured': configured,
            'message': acc.get('message') or (None if configured else '长桥凭据未配置'),
            'totalCash': acc.get('totalCash') if configured else None,
            'netAssets': acc.get('netAssets') if configured else None,
            'availableCash': acc.get('availableCash') if configured else None,
            'currency': acc.get('currency') if configured else None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        await cls._set(cache_key, snapshot)
        return snapshot

    @classmethod
    async def get_position_snapshot(cls, use_scheduled: bool = True) -> dict[str, Any]:
        if use_scheduled:
            scheduled = await cls.get_scheduled('positions')
            if scheduled and scheduled.get('configured') is not None:
                return {
                    'count': scheduled.get('count') or len(scheduled.get('positions') or []),
                    'totalMarketValue': scheduled.get('totalMarketValue'),
                    'totalUnrealizedPnl': scheduled.get('totalUnrealizedPnl'),
                    'positions': scheduled.get('positions') or [],
                    'alerts': scheduled.get('alerts') or [],
                    'timestamp': scheduled.get('asOf'),
                }
        cache_key = 'readmodel:positions'
        cached = await cls._get(cache_key)
        if cached:
            return cached

        pos_res = await LongbridgeService.get_positions_async()
        positions = pos_res.get('positions') or []
        snapshot = {
            'count': len(positions),
            'totalMarketValue': None,
            'totalUnrealizedPnl': None,
            'positions': positions,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        await cls._set(cache_key, snapshot)
        return snapshot

    @classmethod
    async def get_platform_overview_snapshot(cls) -> dict[str, Any]:
        scheduled = await cls.get_scheduled('overview')
        if scheduled:
            scheduled = dict(scheduled)
            scheduled['source'] = 'scheduled'
            return scheduled

        cache_key = 'readmodel:overview'
        cached = await cls._get(cache_key)
        if cached:
            return cached

        asset = await cls.get_account_asset_snapshot(use_scheduled=False)
        pos = await cls.get_position_snapshot(use_scheduled=False)
        factor_scan = await cls.get_scheduled('factors') or {}
        if factor_scan and not factor_scan.get('items') and factor_scan.get('top'):
            factor_scan = dict(factor_scan)
            factor_scan['items'] = factor_scan.get('top') or []
            factor_scan.pop('top', None)
        board = await cls.get_scheduled('board') or {}
        configured = bool(asset.get('configured'))
        snapshot = {
            'configured': configured,
            'message': asset.get('message') or (None if configured else '长桥凭据未配置'),
            'asset': asset,
            'position': pos if configured else {'count': 0, 'positions': [], 'totalMarketValue': None, 'totalUnrealizedPnl': None},
            'factorScan': factor_scan,
            'board': {'count': board.get('count'), 'asOf': board.get('asOf'), 'items': (board.get('items') or [])[:16]},
            'readModelVersion': 'v2.3',
            'refreshTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'live',
        }
        await cls._set(cache_key, snapshot)
        return snapshot
