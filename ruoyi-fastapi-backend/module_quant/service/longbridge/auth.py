"""
长桥凭据与运行时共享状态。

设计要点：
- 凭据来源优先级：当前用户 DB 行 >（无用户上下文时管理员 user_id=1）> LongbridgeConfig(env)。
- 请求级凭据存放在 ContextVar，避免并发请求互相覆盖。
- 全局限频状态（锁 + 上次调用时间）供行情/交易两个客户端共用。
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from contextvars import ContextVar
from typing import Any

from module_quant.service.longbridge.errors import note_sdk_error
from module_quant.service.longbridge.region import endpoints, resolve_region
from module_quant.service.longbridge_quote import is_auth_denied
from utils.log_util import logger
from utils.longbridge_breaker import LongbridgeBreaker

ADMIN_LONGBRIDGE_USER_ID = 1

# 缓存 TTL（秒）；券商返回空结果时写更短的负缓存，防止穿透触发限频
QUOTE_CACHE_TTL = 15
QUOTE_NEGATIVE_CACHE_TTL = 30
ACCOUNT_CACHE_TTL = 30
DEPTH_CACHE_TTL = 3
TRADES_CACHE_TTL = 3
SNAPSHOT_CACHE_TTL = 60

# 全局最小调用间隔（限频）
LB_MIN_INTERVAL = 0.12
# Longbridge QuoteContext.quote returns 301607 when the batch is too large.
QUOTE_SYMBOL_LIMIT = 100
_lb_lock = asyncio.Lock()
_lb_last_call = 0.0

_request_credentials: ContextVar[dict[str, str] | None] = ContextVar(
    'longbridge_request_credentials', default=None
)


def peek_request_user_id() -> int | None:
    """读取请求上下文中的登录用户；后台任务无上下文时返回 None。"""
    try:
        from common.context import current_user
    except Exception as exc:  # pragma: no cover - 导入失败属环境异常
        logger.debug(f'[长桥] 请求上下文模块不可用: {exc}')
        return None
    try:
        ctx = current_user.get()
        user_id = getattr(getattr(ctx, 'user', None), 'user_id', None)
        if user_id:
            return int(user_id)
    except (TypeError, ValueError) as exc:
        logger.debug(f'[长桥] 请求上下文用户ID非法: {exc}')
    return None


def resolve_longbridge_user_id(user_id: int | None = None) -> int:
    """解析长桥凭据所属用户：显式 user_id > 请求用户 > 管理员(1)。"""
    if user_id is not None:
        return int(user_id)
    peeked = peek_request_user_id()
    if peeked is not None:
        return peeked
    return ADMIN_LONGBRIDGE_USER_ID


def decrypt_or_raw(value: str | None) -> str:
    """解密凭据；兼容历史明文存量（解密失败按原值返回）。"""
    if not value:
        return ''
    try:
        from utils.crypto_util import CryptoUtil

        return CryptoUtil.decrypt(value)
    except Exception as exc:
        # 历史明文凭据解密必然失败，属预期路径，用 debug 避免刷屏
        logger.debug(f'[长桥] 凭据解密失败，按明文使用: {exc}')
        return str(value)


class CredentialsMixin:
    """凭据解析/注入相关方法，由 LongbridgeService 组合继承。"""

    _auth_fail_until: float = 0.0
    _AUTH_FAIL_COOLDOWN = 180.0
    _AUTH_CUTOFF_AFTER = 3
    _auth_fail_count: int = 0
    _auth_cut_off: bool = False
    _auth_cut_off_sig: str | None = None

    @classmethod
    def _reset_auth_breaker(cls) -> None:
        cls._auth_fail_until = 0.0
        cls._auth_fail_count = 0
        cls._auth_cut_off = False
        cls._auth_cut_off_sig = None

    @classmethod
    def _auth_blocked(cls) -> str | None:
        """401004 后短路；连续失败则切断，直到 token 更换。"""
        if getattr(cls, '_auth_cut_off', False):
            return '长桥 token 连续失败，已切断远程调用，更换有效 token 后恢复'
        until = float(getattr(cls, '_auth_fail_until', 0) or 0)
        if time.time() < until:
            remain = max(1, int(until - time.time()))
            return f'长桥 token 失效，已短路 {remain}s'
        return None

    @classmethod
    def _trip_auth(cls, exc: Exception) -> None:
        msg = str(exc)
        auth = (
            is_auth_denied(exc)
            or '401004' in msg
            or '401003' in msg
            or 'token invalid' in msg.lower()
        )
        if not auth:
            return
        cls._auth_fail_count = int(getattr(cls, '_auth_fail_count', 0) or 0) + 1
        n = cls._auth_fail_count
        try:
            sig = cls._get_creds_signature(cls.resolve_credentials())
        except Exception:
            sig = None
        if n >= int(getattr(cls, '_AUTH_CUTOFF_AFTER', 3) or 3):
            cls._auth_cut_off = True
            cls._auth_cut_off_sig = sig
            cls._auth_fail_until = time.time() + 86400 * 7
            cls._clear_cached_contexts()
            logger.warning(f'[长桥] token 连续失败 {n} 次，已切断远程调用，更换 token 后恢复: {exc}')
            return
        cooldown = cls._AUTH_FAIL_COOLDOWN if n == 1 else cls._AUTH_FAIL_COOLDOWN * 3
        cls._auth_fail_until = time.time() + cooldown
        logger.warning(f'[长桥] token 失效第 {n} 次，短路 {int(cooldown)}s: {exc}')

    @classmethod
    def set_credentials(cls, credentials: dict[str, str] | None) -> None:
        """
        设置来自 DB 的凭据覆盖（优先级高于 env，仅作用于当前任务/请求）。
        传 None 清除覆盖。
        """
        if credentials and any(
            credentials.get(k) for k in ('app_key', 'app_secret', 'access_token')
        ):
            _request_credentials.set(credentials)
        else:
            _request_credentials.set(None)
        cls._clear_cached_contexts()
        if getattr(cls, '_auth_cut_off', False):
            try:
                sig = cls._get_creds_signature(cls.resolve_credentials())
            except Exception:
                sig = None
            if sig and sig != getattr(cls, '_auth_cut_off_sig', None):
                logger.info('[长桥] 检测到新 token，解除切断')
                cls._reset_auth_breaker()

    @classmethod
    def resolve_credentials(cls) -> dict[str, str]:
        """
        解析当前生效凭据：请求级 DB 覆盖 > env(LongbridgeConfig)。
        """
        override = _request_credentials.get()
        if override:
            creds = override
            return {
                'app_key': str(creds.get('app_key') or ''),
                'app_secret': str(creds.get('app_secret') or ''),
                'access_token': str(creds.get('access_token') or ''),
                'region': resolve_region(creds.get('region')),
                'source': 'db',
                'user_id': str(creds.get('user_id') or ''),
            }
        try:
            from config.env import LongbridgeConfig

            return {
                'app_key': str(LongbridgeConfig.longport_app_key or ''),
                'app_secret': str(LongbridgeConfig.longport_app_secret or ''),
                'access_token': str(LongbridgeConfig.longport_access_token or ''),
                'region': resolve_region(LongbridgeConfig.longport_region),
                'source': 'env',
                'user_id': '',
            }
        except Exception as exc:  # pragma: no cover
            logger.warning(f'[长桥] 读取env凭据失败: {exc}')
            return {
                'app_key': '',
                'app_secret': '',
                'access_token': '',
                'region': 'cn',
                'source': 'none',
                'user_id': '',
            }

    @classmethod
    def is_configured(cls) -> bool:
        """是否已配置有效凭据（三要素齐全）。"""
        creds = cls.resolve_credentials()
        return bool(creds['app_key'] and creds['app_secret'] and creds['access_token'])

    @classmethod
    def _get_creds_signature(cls, creds: dict[str, str]) -> str:
        """计算凭证摘要用于缓存失效检测"""
        return (
            f"{creds.get('user_id')}:{creds.get('app_key')}:{creds.get('app_secret')}:"
            f"{creds.get('access_token')}:{creds.get('region')}"
        )

    @classmethod
    def _creds_cache_tag(cls) -> str:
        """账户/持仓缓存分片：按用户或凭据摘要隔离，避免串号。"""
        creds = cls.resolve_credentials()
        user_id = str(creds.get('user_id') or '').strip()
        if user_id:
            return f'u{user_id}'
        token = creds.get('access_token') or creds.get('app_key') or 'none'
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()[:12]
        return f'e{digest}'

    @classmethod
    def _build_config(cls) -> Any:
        """
        用当前凭据构建 longport 的 Config（延迟导入）。凭据不全返回 None。
        """
        creds = cls.resolve_credentials()
        if not (creds['app_key'] and creds['app_secret'] and creds['access_token']):
            return None
        region = creds['region']
        eps = endpoints(region)
        from longport.openapi import Config, Language  # 延迟导入

        return Config.from_apikey(
            app_key=creds['app_key'],
            app_secret=creds['app_secret'],
            access_token=creds['access_token'],
            http_url=eps['http_url'],
            quote_ws_url=eps['quote_ws_url'],
            trade_ws_url=eps['trade_ws_url'],
            language=Language.ZH_CN,
            enable_overnight=True,
        )

    @classmethod
    def _blocked(cls) -> bool:
        if cls._auth_blocked():
            return True
        return not LongbridgeBreaker.allow()

    @classmethod
    def _clear_cached_contexts(cls) -> None:
        """清理已缓存的上下文对象（定义在 quote/trade 客户端 Mixin 上）。"""
        cls._cached_quote_ctxs.clear()
        cls._cached_trade_ctxs.clear()
        cls._cached_content_ctxs.clear()

    @classmethod
    async def ensure_credentials_from_db(cls, query_db: Any, user_id: int | None = None) -> None:
        """
        从 quant_longbridge_config 注入当前用户凭据（DB 优先）。
        有登录用户时只读该用户行；无用户上下文时回退管理员 user_id=1，再交给 env。
        """
        try:
            from module_quant.dao.quant_dao import (
                QuantLongbridgeConfigDao,
            )

            target_id = resolve_longbridge_user_id(user_id)
            config = await QuantLongbridgeConfigDao.get_config(query_db, target_id)
            if config and (config.app_key or config.app_secret or config.access_token):
                cls.set_credentials(
                    {
                        'app_key': config.app_key or '',
                        'app_secret': decrypt_or_raw(config.app_secret),
                        'access_token': decrypt_or_raw(config.access_token),
                        'region': config.region,
                        'user_id': str(getattr(config, 'user_id', None) or target_id),
                    }
                )
            else:
                cls.set_credentials(None)
        except Exception as exc:
            logger.warning(f'[长桥] 从DB加载凭据失败: {exc}')
            cls.set_credentials(None)

    @classmethod
    def _note_sdk_error(cls, exc: BaseException) -> None:
        """记录一次 SDK 调用失败（熔断计数），统一委托给 errors.note_sdk_error。"""
        note_sdk_error(exc)

    @classmethod
    async def _throttle(cls) -> None:
        global _lb_last_call  # noqa: PLW0603 - 模块级限频时间戳，锁内更新
        async with _lb_lock:
            now = time.monotonic()
            wait = LB_MIN_INTERVAL - (now - _lb_last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            _lb_last_call = time.monotonic()


