"""版本检查接口回归：semver 比较与升级策略计算。"""

import asyncio
import os
import sys
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_admin.controller.app_version_controller import compare_semver


def test_compare_semver():
    assert compare_semver('1.0.0', '1.0.0') == 0
    assert compare_semver('1.0.0', '1.1.0') < 0
    assert compare_semver('2.0', '1.9.9') > 0
    assert compare_semver('1.10.0', '1.9.0') > 0  # 数值比较而非字典序
    assert compare_semver('', '1.0.0') < 0  # 非法当前版本按 0
    assert compare_semver('abc', '1.0.0') < 0


def _make_request(redis_map):
    class _FakeRedis:
        async def get(self, key):
            return redis_map.get(key)

    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_FakeRedis())))


def test_check_version_strategy():
    from module_admin.controller.app_version_controller import check_version

    request = _make_request(
        {
            'sys_config:app.version.android.latest': b'1.2.0',
            'sys_config:app.version.android.min': b'1.1.0',
            'sys_config:app.version.android.url': b'https://example.com/app.apk',
            'sys_config:app.version.android.notes': '修复若干问题'.encode(),
        }
    )

    def run(version):
        return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            check_version(request=request, platform='android', version=version)
        )

    # 落后于 min → 强更
    body = run('1.0.0')
    data = body.body and __import__('json').loads(body.body)
    assert data['data']['updateAvailable'] is True
    assert data['data']['forceUpdate'] is True

    # 高于 min 但低于 latest → 可选升级
    body = run('1.1.5')
    data = __import__('json').loads(body.body)
    assert data['data']['updateAvailable'] is True
    assert data['data']['forceUpdate'] is False

    # 已是最新 → 不提示
    body = run('1.2.0')
    data = __import__('json').loads(body.body)
    assert data['data']['updateAvailable'] is False
    assert data['data']['forceUpdate'] is False


def test_check_version_platform_without_release():
    from module_admin.controller.app_version_controller import check_version

    request = _make_request({})
    body = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        check_version(request=request, platform='ios', version='1.0.0')
    )
    data = __import__('json').loads(body.body)
    assert data['data']['updateAvailable'] is False
    assert data['data']['latestVersion'] == ''
