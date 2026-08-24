"""客户端版本检查接口（M5 发布工程）。

公开端点（无 PreAuth）：应用在登录前后都应能检查更新。
版本基线存于 sys_config，管理员可在 Web 端「系统设置-参数设置」直接调整，无需发版：

    app.version.android.latest   如 1.1.0
    app.version.android.min      如 1.0.5   （低于该版本 → forceUpdate=true）
    app.version.android.url      如 https://example.com/app/app-release.apk
    app.version.android.notes    升级说明（可选）
    （ios / macos / windows 同构）

未配置 latest 时视为该平台暂无发布，返回 updateAvailable=false。
"""

import re
from typing import Annotated, Literal

from fastapi import Request, Response
from utils.response_util import ResponseUtil

from common.router import APIRouterPro

app_version_controller = APIRouterPro(prefix='/app', order_num=3, tags=['客户端版本'])

_PLATFORMS = ('android', 'ios', 'macos', 'windows')

_SEMVER_RE = re.compile(r'^\d+(\.\d+){0,3}$')


def compare_semver(current: str, target: str) -> int:
    """逐段比较点分版本号；非法段按 0 处理。返回 -1/0/1。"""
    def parts(v: str) -> list[int]:
        if not _SEMVER_RE.match((v or '').strip()):
            return [0]
        return [int(p) for p in v.strip().split('.')]

    a, b = parts(current), parts(target)
    width = max(len(a), len(b))
    a += [0] * (width - len(a))
    b += [0] * (width - len(b))
    for x, y in zip(a, b):
        if x != y:
            return -1 if x < y else 1
    return 0


def _config_text(raw) -> str:
    """Redis 缓存值可能是 bytes，归一为去空白字符串。"""
    if raw is None:
        return ''
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode('utf-8', errors='replace')
    return str(raw).strip()


@app_version_controller.get('/version', summary='客户端版本检查')
async def check_version(
    request: Request,
    platform: Annotated[Literal['android', 'ios', 'macos', 'windows'], None] = 'android',
    version: str = '',
) -> Response:
    """
    查询指定平台的最新版本与升级策略。

    :param platform: 目标平台 android/ios/macos/windows
    :param version: 客户端当前版本号（点分数字，如 1.0.0）
    """
    redis = request.app.state.redis

    async def cfg(key_suffix: str) -> str:
        raw = await redis.get(f'sys_config:app.version.{platform}.{key_suffix}')
        return _config_text(raw)

    latest = await cfg('latest')
    minimum = await cfg('min')
    url = await cfg('url')
    notes = await cfg('notes')

    current_valid = bool(_SEMVER_RE.match((version or '').strip()))
    update_available = bool(latest) and current_valid and compare_semver(version, latest) < 0
    force_update = (
        update_available
        and bool(minimum)
        and compare_semver(version, minimum) < 0
    )

    return ResponseUtil.success(
        data={
            'platform': platform,
            'currentVersion': version if current_valid else '',
            'latestVersion': latest,
            'downloadUrl': url,
            'notes': notes,
            'updateAvailable': update_available,
            'forceUpdate': force_update,
        }
    )
