import os
import re
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_job105_seed_is_enabled_not_paused() -> None:
    sql_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'sql', 'quant-phase2-snapshots.sql'
    )
    with open(sql_path, encoding='utf-8') as fh:
        sql = fh.read()
    match = re.search(
        r"\(105,\s*'全市场因子日扫'.*?,\s*'3',\s*'1',\s*'([01])'",
        sql,
        re.DOTALL,
    )
    assert match, 'Job 105 INSERT not found in quant-phase2-snapshots.sql'
    assert match.group(1) == '0', 'Job 105 must be seeded with status=0 (正常/启用)'
    assert "UPDATE sys_job SET status = '0' WHERE job_id = 105" in sql


@pytest.mark.asyncio
async def test_build_factor_scan_payload_prefers_db_rows() -> None:
    from module_quant.service.snapshot_service import SnapshotService

    stored = {'asOf': '2026-08-21', 'symbolCount': 12, 'top': [{'symbol': 'AAPL', 'total': 70}]}
    db_rows = [{'symbol': f'SYM{i}', 'market': 'US', 'total': float(i)} for i in range(34)]

    with patch.object(
        SnapshotService, 'list_factor_snapshots', new=AsyncMock(return_value=db_rows)
    ):
        payload = await SnapshotService.build_factor_scan_payload(MagicMock(), stored)

    assert len(payload['items']) == 34
    assert payload['symbolCount'] == 34
    assert 'top' not in payload
    assert payload['asOf'] == '2026-08-21'


@pytest.mark.asyncio
async def test_build_factor_scan_payload_legacy_top_fallback() -> None:
    from module_quant.service.snapshot_service import SnapshotService

    stored = {'asOf': '2026-08-21', 'top': [{'symbol': 'MSFT', 'total': 55}]}

    with patch.object(SnapshotService, 'list_factor_snapshots', new=AsyncMock(return_value=[])):
        payload = await SnapshotService.build_factor_scan_payload(MagicMock(), stored)

    assert payload['items'] == [{'symbol': 'MSFT', 'total': 55}]
    assert 'top' not in payload


@pytest.mark.asyncio
async def test_list_risk_events_empty_is_real_not_error() -> None:
    from module_trade.service.platform_ext_service import PlatformExtService

    db = MagicMock()
    with (
        patch.object(PlatformExtService, 'ensure_seed_data', new=AsyncMock()),
        patch(
            'module_trade.service.platform_ext_service.TradeDao.expire_overdue_risk_events',
            new=AsyncMock(return_value=0),
        ),
        patch(
            'module_trade.service.platform_ext_service.TradeDao.list_risk_events',
            new=AsyncMock(return_value=[]),
        ),
    ):
        items = await PlatformExtService.list_risk_events(db, limit=50, user_id=1)

    assert items == []


@pytest.mark.asyncio
async def test_list_risk_events_db_error_returns_empty() -> None:
    from module_trade.service.platform_ext_service import PlatformExtService

    db = MagicMock()
    with (
        patch.object(PlatformExtService, 'ensure_seed_data', new=AsyncMock()),
        patch(
            'module_trade.service.platform_ext_service.TradeDao.expire_overdue_risk_events',
            new=AsyncMock(side_effect=RuntimeError('no such table')),
        ),
    ):
        items = await PlatformExtService.list_risk_events(db, limit=50, user_id=1)

    assert items == []
