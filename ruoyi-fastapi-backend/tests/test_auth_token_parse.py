"""鉴权回归：残缺 Bearer 头必须返回 AuthException（→401），而非未捕获 IndexError（→500）。

背景：客户端在未登录态可能发送「Authorization: Bearer」或「Bearer 」空令牌头；
修复前 token.split(' ')[1] 抛 IndexError，经全局兜底处理器返回 code:500，
误导客户端重试而非引导重新登录。
"""

import asyncio
import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from exceptions.exception import AuthException
from module_admin.service.login_service import LoginService

def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_malformed_bearer_raises_auth_exception():
    for bad_token in ('Bearer', 'Bearer ', 'Bearer   '):
        try:
            _run(LoginService.get_current_user(request=None, token=bad_token, query_db=None))
        except AuthException as e:
            assert 'token不合法' in e.message, bad_token
        else:
            raise AssertionError(f'{bad_token!r} 应抛 AuthException')


def test_garbage_token_raises_auth_exception():
    # 非法 JWT 走 InvalidTokenError 分支，同样应归一为 AuthException。
    try:
        _run(LoginService.get_current_user(request=None, token='not-a-jwt', query_db=None))
    except AuthException:
        pass
    else:
        raise AssertionError('非法 JWT 应抛 AuthException')
