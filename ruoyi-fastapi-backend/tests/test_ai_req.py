import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_ai.dao.ai_req_dao import EXCLUDED_USERNAMES
from module_ai.service.ai_req_service import AiReqService, extract_requirement_payload


def test_excluded_usernames() -> None:
    assert 'admin' in EXCLUDED_USERNAMES
    assert 'niangao' in EXCLUDED_USERNAMES
    assert AiReqService.is_member('lusd') is True
    assert AiReqService.is_member('admin') is False
    assert AiReqService.is_member('Niangao') is False


def test_extract_requirement_payload() -> None:
    text = '可行。建议先做列表导出。\n{"action":"upsert_requirements","items":[{"title":"需求清单导出","detail":"提供 JSON 接口","priority":"P1"}]}'
    items = extract_requirement_payload(text)
    assert len(items) == 1
    assert items[0]['title'] == '需求清单导出'
    assert items[0]['priority'] == 'P1'


def test_extract_ignores_plain_chat() -> None:
    assert extract_requirement_payload('这个需求范围太大，建议拆开。') == []
