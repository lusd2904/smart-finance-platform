"""通知 / 风控 / 回测按 user_id 隔离。"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_trade.dao.trade_dao import TradeDao
from module_trade.service.platform_ext_service import PlatformExtService
from module_trade.service.trade_service import TradeService


def test_dao_lists_empty_without_user() -> None:
    async def _run() -> None:
        db = MagicMock()
        assert await TradeDao.list_notifications(db, user_id=None) == []
        assert await TradeDao.list_backtest_runs(db, user_id=None) == []
        assert await TradeDao.list_risk_events(db, user_id=None) == []
        assert await TradeDao.mark_notifications_read(db, user_id=None) == 0
        assert await TradeDao.get_backtest_run_by_id(db, 1, user_id=None) is None
        assert await TradeDao.get_risk_event(db, 1, user_id=None) is None
        assert await TradeDao.update_risk_event_status(db, 1, user_id=None) is False
        db.execute.assert_not_called()

    asyncio.run(_run())


def test_evaluate_risk_without_user_does_not_scan() -> None:
    async def _run() -> None:
        data = await PlatformExtService.evaluate_risk(MagicMock(), user_id=None)
        assert data['created'] == 0
        assert data['signalsChecked'] == 0
        assert '无法识别' in (data.get('message') or '')

    asyncio.run(_run())


def test_list_risk_and_notices_without_user_are_empty() -> None:
    async def _run() -> None:
        db = MagicMock()
        assert await PlatformExtService.list_risk_events(db, user_id=None) == []
        assert await PlatformExtService.list_notices_db(db, user_id=None) == []
        assert await PlatformExtService.mark_notice_read_db(db, user_id=None) == 0

    asyncio.run(_run())


def test_run_backtest_without_user_refuses() -> None:
    async def _run() -> None:
        data = await TradeService.run_backtest_services(MagicMock(), symbol='AAPL', user_id=None)
        assert data['ok'] is False
        assert '无法识别' in data['message']

    asyncio.run(_run())


def test_user_notice_skips_missing_user_id() -> None:
    async def _run() -> None:
        from utils.job_queue import _user_notice

        result = await _user_notice({'title': 'x', 'content': 'y'})
        assert result['ok'] is False
        assert result.get('skipped') is True

    asyncio.run(_run())


def test_evaluate_risk_with_user_queries_signals() -> None:
    async def _run() -> None:
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        result_proxy = MagicMock()
        result_proxy.scalars.return_value.all.return_value = []
        db.execute.return_value = result_proxy
        with (
            patch.object(PlatformExtService, 'ensure_seed_data', new=AsyncMock()),
            patch.object(PlatformExtService, 'list_risk_rules', new=AsyncMock(return_value=[])),
        ):
            data = await PlatformExtService.evaluate_risk(db, user_id=42)
        assert data['created'] == 0
        assert data['signalsChecked'] == 0
        db.execute.assert_awaited()

    asyncio.run(_run())
