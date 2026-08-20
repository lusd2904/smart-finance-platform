from datetime import datetime
from typing import Any

from module_quant.service.longbridge_service import LongbridgeService
from utils.json_cache import cache_get_json, cache_set_json

_CACHE_TTL = 30
_MEMORY: dict[str, dict[str, Any]] = {}


def _memory_get(key: str) -> Any | None:
    entry = _MEMORY.get(key)
    if not entry:
        return None
    ts = entry.get('timestamp') or 0
    if (datetime.now().timestamp() - ts) >= _CACHE_TTL:
        return None
    return entry.get('data')


def _memory_set(key: str, data: Any) -> None:
    _MEMORY[key] = {'data': data, 'timestamp': datetime.now().timestamp()}


class ReadModelService:
    """
    读模型快照：优先 Redis，失败回退进程内 30s 缓存。
    """

    @classmethod
    async def _get(cls, key: str) -> Any | None:
        cached = await cache_get_json(key)
        if cached is not None:
            return cached
        return _memory_get(key)

    @classmethod
    async def _set(cls, key: str, data: Any) -> None:
        _memory_set(key, data)
        await cache_set_json(key, data, _CACHE_TTL)

    @classmethod
    async def get_account_asset_snapshot(cls) -> dict[str, Any]:
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
    async def get_position_snapshot(cls) -> dict[str, Any]:
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
        cache_key = 'readmodel:overview'
        cached = await cls._get(cache_key)
        if cached:
            return cached

        asset = await cls.get_account_asset_snapshot()
        pos = await cls.get_position_snapshot()
        configured = bool(asset.get('configured'))
        snapshot = {
            'configured': configured,
            'message': asset.get('message') or (None if configured else '长桥凭据未配置'),
            'asset': asset,
            'position': pos if configured else {'count': 0, 'positions': [], 'totalMarketValue': None, 'totalUnrealizedPnl': None},
            'readModelVersion': 'v2.2',
            'refreshTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        await cls._set(cache_key, snapshot)
        return snapshot
