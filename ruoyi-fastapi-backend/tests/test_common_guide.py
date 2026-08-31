"""GET /common/guide/{module}：白名单本地 Markdown，无网络。"""

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_admin.service.common_service import GUIDE_DIR, GUIDE_MODULES, load_guide


def test_load_known_module_if_file_exists() -> None:
    loaded = False
    for module in GUIDE_MODULES:
        data = load_guide(module)
        if data is None:
            continue
        loaded = True
        assert data['module'] == module
        assert data['markdown']
        assert data['title']
    if not loaded:
        assert not (GUIDE_DIR / 'market.md').is_file()
        assert load_guide('market') is None


def test_load_known_module_from_fixture(tmp_path: Path, monkeypatch) -> None:
    from module_admin.service import common_service as svc

    guides = tmp_path / 'guides'
    guides.mkdir()
    (guides / 'market.md').write_text('# 行情中心\n\nhello', encoding='utf-8')
    monkeypatch.setattr(svc, 'GUIDE_DIR', guides)

    data = svc.load_guide('market')
    assert data is not None
    assert data['module'] == 'market'
    assert data['title'] == '行情中心'
    assert data['markdown'] == '# 行情中心\n\nhello'


def test_reject_path_traversal() -> None:
    assert load_guide('../etc/passwd') is None
    assert load_guide('..\\etc\\passwd') is None


def test_reject_unknown_module() -> None:
    assert load_guide('foo') is None


def test_controller_rejects_unknown_and_traversal() -> None:
    from module_admin.controller.common_controller import common_guide

    for module in ('foo', '../etc/passwd'):
        body = json.loads(asyncio.run(common_guide(request=None, module=module)).body)
        assert body['success'] is False
        assert body['msg'] == '说明不存在'
        assert body['code'] == 601
