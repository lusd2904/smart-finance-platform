import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import true

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_ai.dao.ai_model_dao import AiModelDao
from module_ai.entity.vo.ai_model_vo import AiModelModel, AiModelPageQueryModel
from module_ai.service.ai_model_service import AiModelService


def test_get_ai_model_list_accepts_plain_ai_model_model() -> None:
    async def _run() -> None:
        db = MagicMock()
        paginate = AsyncMock(return_value=[{'modelId': 7}])
        with patch('module_ai.dao.ai_model_dao.PageUtil.paginate', paginate):
            rows = await AiModelDao.get_ai_model_list(
                db, AiModelModel(modelId=7), true(), is_page=False
            )
        assert rows == [{'modelId': 7}]
        _db, _query, page_num, page_size, is_page = paginate.await_args.args
        assert page_num == 1
        assert page_size == 10
        assert is_page is False

    asyncio.run(_run())


def test_data_scope_check_passes_page_query_model() -> None:
    async def _run() -> None:
        db = MagicMock()
        get_list = AsyncMock(return_value=[{'modelId': 3}])
        with patch('module_ai.service.ai_model_service.AiModelDao.get_ai_model_list', get_list):
            result = await AiModelService.check_ai_model_data_scope_services(db, 3, MagicMock())
        assert result.is_success is True
        query_object = get_list.await_args.args[1]
        assert isinstance(query_object, AiModelPageQueryModel)
        assert query_object.model_id == 3
        assert query_object.page_num == 1
        assert query_object.page_size == 10

    asyncio.run(_run())
