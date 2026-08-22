from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.env import AppConfig


def _cors_allow_origins() -> list[str]:
    """
    解析 CORS 白名单。

    优先读 APP_CORS_ORIGINS（逗号分隔）。未配置时：
    - dev 环境回退为允许所有来源但关闭凭证（本地开发便利性）
    - prod 环境直接拒绝启动，强制显式配置白名单

    :return: 来源列表
    """
    raw = getattr(AppConfig, 'app_cors_origins', '')
    origins = [o.strip().rstrip('/') for o in raw.split(',') if o.strip()]
    if origins:
        return origins
    if AppConfig.app_env == 'prod':
        raise RuntimeError(
            "安全检查失败：生产环境必须配置 APP_CORS_ORIGINS 域名白名单"
            "（逗号分隔，如 https://fin.example.com），禁止全开放跨域。"
        )
    return ['*']


def add_cors_middleware(app: FastAPI) -> None:
    """
    添加跨域中间件

    :param app: FastAPI对象
    :return:
    """
    # 前端页面url：显式白名单；dev 未配置时放开来源但不携带凭证
    origins = _cors_allow_origins()
    wildcard = origins == ['*']
    expose_headers = [
        'x-body-encrypted',
        'x-key-id',
        'x-encrypt-alg',
    ]

    # 后台api允许跨域：allow_origins='*' 与 allow_credentials=True 组合会回显任意 Origin，
    # 等于关闭跨域防护，二者不可同时开启。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not wildcard,
        allow_methods=['*'],
        allow_headers=['*'],
        expose_headers=expose_headers,
    )
