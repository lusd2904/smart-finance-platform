"""
长桥调用熔断。

401004 / 凭证失效立即开闸；超时累计后开闸。开闸期间所有进程不再打长桥。
禁止自动 refresh token。

凭据保存后通过 Redis `sfp:lb:creds_epoch` 通知其他进程：本地 seen epoch
落后时清除本进程切断/熔断/缓存，不刷新 token。
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from utils.log_util import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

REDIS_KEY = 'sfp:lb:circuit'
CREDS_EPOCH_KEY = 'sfp:lb:creds_epoch'
OPEN_SECONDS_AUTH = 300
OPEN_SECONDS_TIMEOUT = 120
TIMEOUT_FAILS_TO_OPEN = 2
TIMEOUT_WINDOW_SECONDS = 30

_epoch_listeners: list[Callable[[int], None]] = []


def is_auth_failure(exc: BaseException | str | None) -> bool:
    text = str(exc or '')
    lowered = text.lower()
    if '401004' in text:
        return True
    if '401' in text and ('unauth' in lowered or 'token' in lowered or 'access' in lowered):
        return True
    if 'unauthorized' in lowered or 'unauth' in lowered:
        return True
    if 'token' in lowered and any(word in lowered for word in ('invalid', 'expired', '失效', '过期')):
        return True
    return bool('凭证失效' in text or '令牌无效' in text)


def is_timeout_failure(exc: BaseException | str | None) -> bool:
    text = str(exc or '').lower()
    return any(token in text for token in ('timeout', 'timed out', 'time out', 'deadline', '超时'))


def _notify_epoch_listener(listener: Callable[[int], None], remote: int) -> None:
    try:
        listener(remote)
    except Exception as exc:
        logger.debug(f'[长桥熔断] creds_epoch 回调失败: {exc}')


def register_creds_epoch_listener(fn: Callable[[int], None]) -> Callable[[int], None]:
    """注册 creds_epoch 前进时的本进程回调（清切断/缓存）。"""
    if fn not in _epoch_listeners:
        _epoch_listeners.append(fn)
    return fn


def _redis_client() -> Any:
    try:
        from config.get_redis import RedisUtil

        return RedisUtil.get_client()
    except Exception:
        return None


def _close_coro(coro: Any) -> None:
    closer = getattr(coro, 'close', None)
    if callable(closer):
        try:
            closer()
        except Exception:
            return


def _log_redis_task(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.debug(f'[长桥熔断] Redis 任务失败: {exc}')


def _schedule_redis(coro: Awaitable[Any] | None) -> None:
    """调度异步 Redis 命令：有事件循环则 create_task，否则 asyncio.run。禁止丢弃未 await 的协程。"""
    if coro is None or not hasattr(coro, '__await__'):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception as exc:
            logger.debug(f'[长桥熔断] Redis 同步执行失败: {exc}')
        return
    try:
        task = loop.create_task(coro)  # type: ignore[arg-type]
        task.add_done_callback(_log_redis_task)
    except Exception as exc:
        logger.debug(f'[长桥熔断] Redis 调度失败: {exc}')
        _close_coro(coro)


class LongbridgeBreaker:
    _open_until: float = 0.0
    _reason: str = ''
    _timeout_fails: list[float] = []
    _seen_creds_epoch: int = 0
    _cached_remote_epoch: int = 0
    _epoch_refresh_pending: bool = False

    @classmethod
    def reset(cls) -> None:
        cls._open_until = 0.0
        cls._reason = ''
        cls._timeout_fails = []

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        open_now = not cls.allow()
        remaining = max(0, int(cls._open_until - time.monotonic())) if open_now else 0
        return {
            'open': open_now,
            'reason': cls._reason if open_now else '',
            'remainingSeconds': remaining,
        }

    @classmethod
    def allow(cls) -> bool:
        cls.sync_creds_epoch_if_needed()
        if cls._open_until and time.monotonic() < cls._open_until:
            return False
        if cls._open_until and time.monotonic() >= cls._open_until:
            cls._open_until = 0.0
            cls._reason = ''
        return True

    @classmethod
    def trip(cls, reason: str, seconds: int) -> None:
        until = time.monotonic() + max(5, int(seconds))
        if until > cls._open_until:
            cls._open_until = until
            cls._reason = reason
        logger.warning(f'[长桥熔断] 开闸 reason={reason} seconds={seconds}，期间不再请求长桥')
        cls._persist_open(reason, seconds)

    @classmethod
    def record_success(cls) -> None:
        cls._timeout_fails = []

    @classmethod
    def record_failure(cls, exc: BaseException | str | None) -> None:
        if is_auth_failure(exc):
            cls.trip('unauthorized', OPEN_SECONDS_AUTH)
            return
        if is_timeout_failure(exc):
            now = time.monotonic()
            cls._timeout_fails = [ts for ts in cls._timeout_fails if now - ts <= TIMEOUT_WINDOW_SECONDS]
            cls._timeout_fails.append(now)
            if len(cls._timeout_fails) >= TIMEOUT_FAILS_TO_OPEN:
                cls.trip('timeout', OPEN_SECONDS_TIMEOUT)

    @classmethod
    def blocked_message(cls) -> str:
        reason = cls._reason or 'circuit_open'
        if reason == 'unauthorized':
            return '长桥凭证失效，熔断中，已停止请求（不会自动刷新 token）'
        if reason == 'timeout':
            return '长桥超时熔断中，已停止请求'
        return '长桥熔断中，暂不请求行情'

    @classmethod
    def apply_creds_epoch(cls, remote_epoch: int) -> bool:
        """若 Redis/缓存 epoch 新于本进程，复位熔断并通知监听方清切断与上下文。"""
        remote = int(remote_epoch or 0)
        if remote > int(cls._cached_remote_epoch or 0):
            cls._cached_remote_epoch = remote
        if remote <= int(cls._seen_creds_epoch or 0):
            return False
        cls.reset()
        cls._seen_creds_epoch = remote
        cls._cached_remote_epoch = remote
        for listener in _epoch_listeners:
            _notify_epoch_listener(listener, remote)
        logger.info(f'[长桥熔断] 检测到凭据 epoch={remote}，已清除本进程熔断/切断')
        return True

    @classmethod
    def sync_creds_epoch_if_needed(cls) -> bool:
        """同步路径：应用已缓存的远程 epoch，并在有事件循环时拉取最新值。"""
        applied = cls.apply_creds_epoch(cls._cached_remote_epoch)
        cls._schedule_epoch_refresh()
        return applied

    @classmethod
    def _schedule_epoch_refresh(cls) -> None:
        if cls._epoch_refresh_pending:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        cls._epoch_refresh_pending = True

        async def _refresh() -> None:
            try:
                await cls.pull_creds_epoch()
            finally:
                cls._epoch_refresh_pending = False

        task = loop.create_task(_refresh())
        task.add_done_callback(_log_redis_task)

    @classmethod
    async def read_creds_epoch(cls) -> int:
        redis = _redis_client()
        if redis is None:
            return int(cls._cached_remote_epoch or 0)
        try:
            raw = await redis.get(CREDS_EPOCH_KEY)
        except Exception as exc:
            logger.debug(f'[长桥熔断] 读取 creds_epoch 失败: {exc}')
            return int(cls._cached_remote_epoch or 0)
        if raw is None or raw == '':
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @classmethod
    async def pull_creds_epoch(cls) -> bool:
        remote = await cls.read_creds_epoch()
        return cls.apply_creds_epoch(remote)

    @classmethod
    async def bump_creds_epoch(cls) -> int:
        """保存凭据成功后递增 epoch；本进程直接对齐，避免把自己再清一次。"""
        redis = _redis_client()
        epoch = int(cls._seen_creds_epoch or 0) + 1
        if redis is not None:
            try:
                epoch = int(await redis.incr(CREDS_EPOCH_KEY))
            except Exception as exc:
                logger.debug(f'[长桥熔断] 递增 creds_epoch 失败: {exc}')
        cls._seen_creds_epoch = epoch
        cls._cached_remote_epoch = epoch
        return epoch

    @classmethod
    async def clear_persisted(cls) -> None:
        """删除 Redis 熔断键（保存凭据后调用，必须 await）。"""
        redis = _redis_client()
        if redis is None:
            return
        try:
            await redis.delete(REDIS_KEY)
        except Exception as exc:
            logger.debug(f'[长桥熔断] 删除 circuit 键失败: {exc}')

    @classmethod
    def _persist_open(cls, reason: str, seconds: int) -> None:
        redis = _redis_client()
        if redis is None:
            return
        payload = f'{reason}|{int(time.time()) + int(seconds)}'
        _schedule_redis(cls._setex_circuit(int(seconds), payload))

    @classmethod
    async def _setex_circuit(cls, seconds: int, payload: str) -> None:
        redis = _redis_client()
        if redis is None:
            return
        try:
            await redis.setex(REDIS_KEY, int(seconds), payload)
        except Exception as exc:
            logger.debug(f'[长桥熔断] 写入 circuit 键失败: {exc}')

    @classmethod
    async def hydrate_from_redis(cls) -> None:
        # 启动时只对齐 epoch 水位，不把已有 epoch 当成“刚保存”去清熔断
        try:
            remote = await cls.read_creds_epoch()
            cls._seen_creds_epoch = int(remote or 0)
            cls._cached_remote_epoch = int(remote or 0)
        except Exception:
            pass
        redis = _redis_client()
        if redis is None:
            return
        try:
            raw = await redis.get(REDIS_KEY)
        except Exception:
            return
        if not raw:
            return
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        try:
            reason, until_s = str(raw).split('|', 1)
            remaining = int(until_s) - int(time.time())
        except (TypeError, ValueError):
            return
        if remaining > 0:
            cls._open_until = time.monotonic() + remaining
            cls._reason = reason
