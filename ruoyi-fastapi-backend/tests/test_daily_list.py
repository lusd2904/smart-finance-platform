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
