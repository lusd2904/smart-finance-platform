import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_dashboard.service import dashboard_service
from module_dashboard.service.dashboard_service import DashboardService, _empty


@pytest.mark.asyncio
async def test_asset_block_never_calls_longbridge_when_overview_missing() -> None:
    with (
        patch(
            'module_quant.service.readmodel_service.ReadModelService.get_scheduled',
            new=AsyncMock(return_value=None),
        ),
        patch(
            'module_quant.service.readmodel_service.ReadModelService.get_account_asset_snapshot',
            new=AsyncMock(side_effect=AssertionError('must not hit live Longbridge')),
        ) as live,
    ):
        result = await DashboardService._asset_block(AsyncMock())

    live.assert_not_called()
    assert result['ok'] is True
    assert result['data']['configured'] is False
    assert result['data']['netAssets'] is None
    assert result['data']['message'] == '读模型快照尚未生成'


@pytest.mark.asyncio
async def test_asset_block_uses_scheduled_overview_only() -> None:
    scheduled = {
        'asset': {
            'configured': True,
            'netAssets': 100,
            'availableCash': 20,
            'totalCash': 30,
            'currency': 'HKD',
            'message': None,
        },
        'position': {'count': 3, 'totalUnrealizedPnl': 1.5},
    }
    with (
        patch(
            'module_quant.service.readmodel_service.ReadModelService.get_scheduled',
            new=AsyncMock(return_value=scheduled),
        ),
        patch(
            'module_quant.service.readmodel_service.ReadModelService.get_account_asset_snapshot',
            new=AsyncMock(side_effect=AssertionError('must not hit live Longbridge')),
        ) as live,
    ):
        result = await DashboardService._asset_block(AsyncMock())

    live.assert_not_called()
    assert result['data']['netAssets'] == 100
    assert result['data']['positionCount'] == 3
    assert result['data']['totalUnrealizedPnl'] == 1.5


@pytest.mark.asyncio
async def test_collect_timeout_returns_empty_timeout() -> None:
    async def _hang(_db=None, _user=None):
        await asyncio.sleep(2)
        return {'ok': True, 'reason': None, 'data': {}}

    async def _fast(_db=None, _user=None):
        return {'ok': True, 'reason': None, 'data': {'ok': True}}

    with (
        patch.object(dashboard_service, 'SECTION_TIMEOUT_SEC', 0.05),
        patch.object(DashboardService, '_asset_block', side_effect=_hang),
        patch.object(DashboardService, '_quotes_block', side_effect=_fast),
        patch.object(DashboardService, '_heat_block', side_effect=_fast),
        patch.object(DashboardService, '_watch_signals_block', side_effect=_fast),
        patch.object(DashboardService, '_sentiment_block', side_effect=_fast),
        patch.object(DashboardService, '_briefings_block', side_effect=_fast),
        patch.object(DashboardService, '_health_block', side_effect=_fast),
    ):
        out = await DashboardService._collect(AsyncMock(), user_id=1, has=lambda _perm: True)

    assert out['asset'] == _empty('asset', 'timeout')
    assert out['quotes']['ok'] is True
    assert out['heat']['ok'] is True


@pytest.mark.asyncio
async def test_summary_keeps_30s_cache() -> None:
    cached = {'generatedAt': '2026-08-24 12:00:00', 'asset': {'ok': True}}
    with (
        patch('module_dashboard.service.dashboard_service.cache_get_json', new=AsyncMock(return_value=cached)),
        patch.object(DashboardService, '_collect', new=AsyncMock()) as collect,
        patch('module_dashboard.service.dashboard_service.cache_set_json', new=AsyncMock()) as cache_set,
    ):
        result = await DashboardService.get_summary_services(AsyncMock(), 1, ['*:*:*'], use_cache=True)

    collect.assert_not_called()
    cache_set.assert_not_called()
    assert result['cached'] is True
    assert result['generatedAt'] == '2026-08-24 12:00:00'


@pytest.mark.asyncio
async def test_summary_refresh_rewrites_cache() -> None:
    sections = {key: {'ok': True, 'reason': None, 'data': {}} for key in dashboard_service.SECTION_PERMS}
    with (
        patch('module_dashboard.service.dashboard_service.cache_get_json', new=AsyncMock(return_value=None)),
        patch.object(DashboardService, '_collect', new=AsyncMock(return_value=sections)),
        patch('module_dashboard.service.dashboard_service.cache_set_json', new=AsyncMock()) as cache_set,
    ):
        result = await DashboardService.get_summary_services(AsyncMock(), 1, ['*:*:*'], use_cache=False)

    cache_set.assert_awaited()
    assert cache_set.await_args.args[2] == dashboard_service.SUMMARY_CACHE_TTL
    assert result['cached'] is False
    assert result['generatedAt']


def test_summary_cache_key_includes_user_and_perms() -> None:
    from module_dashboard.service.dashboard_service import summary_cache_key

    a = summary_cache_key(1, ['market:watchlist:list'])
    b = summary_cache_key(2, ['market:watchlist:list'])
    c = summary_cache_key(1, ['*:*:*'])
    assert a.startswith('dashboard:summary:1:')
    assert a != b
    assert a != c


@pytest.mark.asyncio
async def test_summary_cache_does_not_leak_across_users() -> None:
    cached_a = {'generatedAt': '2026-08-24 12:00:00', 'watchSignals': {'data': 'user-a'}}
    seen: list[str] = []

    async def fake_get(key: str):
        seen.append(key)
        if ':1:' in key:
            return cached_a
        return None

    with (
        patch('module_dashboard.service.dashboard_service.cache_get_json', new=fake_get),
        patch.object(
            DashboardService,
            '_collect',
            new=AsyncMock(return_value={'watchSignals': {'data': 'user-b'}}),
        ) as collect,
        patch('module_dashboard.service.dashboard_service.cache_set_json', new=AsyncMock()),
    ):
        first = await DashboardService.get_summary_services(AsyncMock(), 1, ['*:*:*'], use_cache=True)
        second = await DashboardService.get_summary_services(AsyncMock(), 2, ['*:*:*'], use_cache=True)

    assert first['watchSignals']['data'] == 'user-a'
    collect.assert_awaited()
    assert seen[0] != seen[1]
    assert second['watchSignals']['data'] == 'user-b'
