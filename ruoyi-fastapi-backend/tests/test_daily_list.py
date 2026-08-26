import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from exceptions.exception import ServiceException
from module_quant.service.daily_list_service import DailyListService


def test_open_rejects_empty_selection() -> None:
    async def _run() -> None:
        with pytest.raises(ServiceException) as err:
            await DailyListService.open_selected(SimpleNamespace(), 101, [])
        assert '勾选' in (err.value.message or '')

    import asyncio

    asyncio.run(_run())


def test_execute_queued_skips_users_without_account_switch() -> None:
    from unittest.mock import AsyncMock, patch

    async def _run() -> None:
        row = SimpleNamespace(user_id=101, market='US', status='queued', item_id=1)
        db = SimpleNamespace()
        db.commit = AsyncMock()
        with (
            patch(
                'module_quant.service.daily_list_service.QuantDailyListDao.list_queued',
                AsyncMock(return_value=[row]),
            ),
            patch('module_quant.service.daily_list_service.is_market_session_open', return_value=True),
            patch.object(
                DailyListService,
                '_account_trade_ready',
                AsyncMock(return_value=(False, '请先在「量化交易 / 策略配置」打开本账户自动交易')),
            ),
            patch.object(DailyListService, '_place_or_queue', AsyncMock()) as place,
        ):
            res = await DailyListService.execute_queued(db)
        place.assert_not_called()
        assert res['count'] == 0
        assert res['skippedUsers'] == [101]

    import asyncio

    asyncio.run(_run())


def test_open_requires_account_auto_trade() -> None:
    from unittest.mock import AsyncMock, patch

    async def _run() -> None:
        latest = SimpleNamespace(list_id=10, status='open')
        with (
            patch(
                'module_quant.service.daily_list_service.QuantDailyListDao.latest_for_user',
                AsyncMock(return_value=latest),
            ),
            patch.object(
                DailyListService,
                '_account_trade_ready',
                AsyncMock(return_value=(False, '未配置长桥账户 Key，无法打开自动交易')),
            ),
        ):
            with pytest.raises(ServiceException) as err:
                await DailyListService.open_selected(SimpleNamespace(), 101, [1])
        assert 'Key' in (err.value.message or '')

    import asyncio

    asyncio.run(_run())
