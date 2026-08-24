"""
传输层加解密监控统计与聚合

拆分自 utils/transport_crypto_util.py，负责监控计数与失败事件的
Redis聚合写入、进程内回退统计以及监控快照的读取与合并。
"""

import json
import time
from collections import Counter, defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Any

from fastapi import FastAPI
from redis import asyncio as aioredis

from config.env import AppConfig, TransportCryptoConfig
from utils.log_util import logger
from utils.transport_crypto.envelope import TransportCryptoUtil
from utils.transport_crypto.keys import TransportKeyProvider


# 传输层监控读写与聚合
class TransportCryptoMonitorUtil:
    """
    传输层加解密监控工具
    """

    _REDIS_KEY_PREFIX = 'transport:monitor'
    _META_STARTED_AT_KEY = f'{_REDIS_KEY_PREFIX}:started_at'
    _COUNTERS_KEY = f'{_REDIS_KEY_PREFIX}:counters'
    _FAILURE_REASONS_KEY = f'{_REDIS_KEY_PREFIX}:failure_reasons'
    _KIDS_KEY = f'{_REDIS_KEY_PREFIX}:kids'
    _RECENT_FAILURES_KEY = f'{_REDIS_KEY_PREFIX}:recent_failures'
    _RECENT_FAILURE_LIMIT = 20
    _REDIS_WARNING_INTERVAL_SECONDS = 60
    _lock = Lock()
    _started_at = datetime.now()
    _counters: Counter[str] = Counter()
    _failure_reasons: Counter[str] = Counter()
    _kid_counters: defaultdict[str, Counter[str]] = defaultdict(Counter)
    _recent_failures: deque[dict[str, Any]] = deque(maxlen=_RECENT_FAILURE_LIMIT)
    _last_redis_warning_at = 0.0

    # 对外暴露的监控记录与查询入口
    @classmethod
    async def record_plain_request(cls, app: FastAPI | None = None) -> None:
        """
        记录明文请求

        :param app: FastAPI应用对象
        :return: None
        """
        if await cls._write_redis_counters(
            app,
            counter_updates={
                'requests_total': 1,
                'plain_requests_total': 1,
            },
        ):
            return
        cls._record_plain_request_local()

    @classmethod
    async def record_encrypted_request(cls, app: FastAPI | None = None, kid: str | None = None) -> None:
        """
        记录加密请求

        :param app: FastAPI应用对象
        :param kid: 当前请求使用的密钥版本
        :return: None
        """
        if await cls._write_redis_counters(
            app,
            counter_updates={
                'requests_total': 1,
                'encrypted_requests_total': 1,
            },
            kid=kid,
            kid_counter_updates={'encrypted_requests_total': 1},
        ):
            return
        cls._record_encrypted_request_local(kid)

    @classmethod
    async def record_required_rejected(cls, app: FastAPI | None = None, method: str = '', path: str = '') -> None:
        """
        记录强制加密接口被明文访问的拒绝事件

        :param app: FastAPI应用对象
        :param method: 请求方法
        :param path: 请求路径
        :return: None
        """
        if await cls._write_redis_failure(
            app,
            method=method,
            path=path,
            reason='required_missing',
            include_decrypt_failure=False,
        ):
            return
        cls._record_failure_local(method, path, 'required_missing', include_decrypt_failure=False)

    @classmethod
    async def record_decrypt_success(cls, app: FastAPI | None = None, kid: str | None = None) -> None:
        """
        记录请求解密成功事件

        :param app: FastAPI应用对象
        :param kid: 当前请求使用的密钥版本
        :return: None
        """
        if await cls._write_redis_counters(
            app,
            counter_updates={'decrypt_success_total': 1},
            kid=kid,
            kid_counter_updates={'decrypt_success_total': 1},
        ):
            return
        cls._record_decrypt_success_local(kid)

    @classmethod
    async def record_decrypt_failure(
        cls,
        app: FastAPI | None = None,
        method: str = '',
        path: str = '',
        reason: str = '',
        kid: str | None = None,
    ) -> None:
        """
        记录请求解密失败事件

        :param app: FastAPI应用对象
        :param method: 请求方法
        :param path: 请求路径
        :param reason: 失败原因分类
        :param kid: 当前请求使用的密钥版本
        :return: None
        """
        if await cls._write_redis_failure(app, method=method, path=path, reason=reason, kid=kid):
            return
        cls._record_failure_local(method, path, reason, kid=kid)

    @classmethod
    async def record_plain_response(cls, app: FastAPI | None = None) -> None:
        """
        记录明文响应

        :param app: FastAPI应用对象
        :return: None
        """
        if await cls._write_redis_counters(app, counter_updates={'plain_responses_total': 1}):
            return
        cls._record_plain_response_local()

    @classmethod
    async def record_encrypted_response(
        cls,
        app: FastAPI | None = None,
        kid: str | None = None,
        is_error: bool = False,
    ) -> None:
        """
        记录加密响应

        :param app: FastAPI应用对象
        :param kid: 当前响应使用的密钥版本
        :param is_error: 是否为错误响应
        :return: None
        """
        counter_updates = {'encrypted_responses_total': 1}
        if is_error:
            counter_updates['encrypted_error_responses_total'] = 1
        if await cls._write_redis_counters(
            app,
            counter_updates=counter_updates,
            kid=kid,
            kid_counter_updates={'encrypted_responses_total': 1},
        ):
            return
        cls._record_encrypted_response_local(kid, is_error)

    @classmethod
    async def get_snapshot(cls, app: FastAPI | None = None) -> dict[str, Any]:
        """
        获取传输层加解密监控快照

        :param app: FastAPI应用对象
        :return: 监控快照字典
        """
        redis_snapshot = await cls._get_redis_snapshot(app)
        local_snapshot = cls._get_local_snapshot_parts()
        snapshot_parts = cls._merge_snapshot_parts(redis_snapshot, local_snapshot)
        return cls._build_snapshot(snapshot_parts)

    # Redis 聚合写入与读取
    @classmethod
    async def _write_redis_counters(
        cls,
        app: FastAPI | None,
        counter_updates: dict[str, int],
        kid: str | None = None,
        kid_counter_updates: dict[str, int] | None = None,
    ) -> bool:
        """
        将监控计数写入Redis

        :param app: FastAPI应用对象
        :param counter_updates: 全局计数增量
        :param kid: 当前密钥版本
        :param kid_counter_updates: 按密钥版本统计的增量
        :return: 是否写入成功
        """
        redis = cls._get_redis_client(app)
        if redis is None:
            return False
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.set(cls._META_STARTED_AT_KEY, cls._started_at.isoformat(), nx=True)
                for counter_name, delta in counter_updates.items():
                    pipe.hincrby(cls._COUNTERS_KEY, counter_name, delta)
                if kid and kid_counter_updates:
                    pipe.sadd(cls._KIDS_KEY, kid)
                    kid_counter_key = cls._build_kid_counter_key(kid)
                    for counter_name, delta in kid_counter_updates.items():
                        pipe.hincrby(kid_counter_key, counter_name, delta)
                await pipe.execute()
            return True
        except Exception as exc:
            cls._log_redis_warning('write_counters', exc)
            return False

    @classmethod
    async def _write_redis_failure(
        cls,
        app: FastAPI | None,
        method: str,
        path: str,
        reason: str,
        kid: str | None = None,
        include_decrypt_failure: bool = True,
    ) -> bool:
        """
        将失败事件写入Redis

        :param app: FastAPI应用对象
        :param method: 请求方法
        :param path: 请求路径
        :param reason: 失败原因分类
        :param kid: 当前密钥版本
        :param include_decrypt_failure: 是否计入解密失败次数
        :return: 是否写入成功
        """
        redis = cls._get_redis_client(app)
        if redis is None:
            return False
        try:
            recent_failure = json.dumps(
                {
                    'time': datetime.now().isoformat(),
                    'method': method,
                    'path': path,
                    'reason': reason,
                    'kid': kid,
                },
                ensure_ascii=False,
            )
            async with redis.pipeline(transaction=False) as pipe:
                pipe.set(cls._META_STARTED_AT_KEY, cls._started_at.isoformat(), nx=True)
                if include_decrypt_failure:
                    pipe.hincrby(cls._COUNTERS_KEY, 'decrypt_failure_total', 1)
                if reason == 'required_missing':
                    pipe.hincrby(cls._COUNTERS_KEY, 'required_rejected_total', 1)
                pipe.hincrby(cls._FAILURE_REASONS_KEY, reason, 1)
                pipe.lpush(cls._RECENT_FAILURES_KEY, recent_failure)
                pipe.ltrim(cls._RECENT_FAILURES_KEY, 0, cls._RECENT_FAILURE_LIMIT - 1)
                if kid:
                    pipe.sadd(cls._KIDS_KEY, kid)
                    pipe.hincrby(cls._build_kid_counter_key(kid), 'decrypt_failure_total', 1)
                await pipe.execute()
            return True
        except Exception as exc:
            cls._log_redis_warning('write_failure', exc)
            return False

    @classmethod
    async def _get_redis_snapshot(cls, app: FastAPI | None) -> dict[str, Any]:
        """
        从Redis中读取监控快照

        :param app: FastAPI应用对象
        :return: Redis监控快照字典
        """
        redis = cls._get_redis_client(app)
        if redis is None:
            return {
                'monitor_scope': 'process-local-fallback',
                'started_at': cls._started_at,
                'counters': {},
                'failure_reasons': {},
                'kid_stats': [],
                'recent_failures': [],
            }
        try:
            async with redis.pipeline(transaction=False) as pipe:
                pipe.set(cls._META_STARTED_AT_KEY, cls._started_at.isoformat(), nx=True)
                pipe.get(cls._META_STARTED_AT_KEY)
                pipe.hgetall(cls._COUNTERS_KEY)
                pipe.hgetall(cls._FAILURE_REASONS_KEY)
                pipe.lrange(cls._RECENT_FAILURES_KEY, 0, cls._RECENT_FAILURE_LIMIT - 1)
                pipe.smembers(cls._KIDS_KEY)
                _, started_at_raw, counters_raw, failure_reasons_raw, recent_failures_raw, kids = await pipe.execute()
            kid_stats = await cls._get_redis_kid_stats(redis, sorted(kids))
            return {
                'monitor_scope': 'redis-aggregated',
                'started_at': cls._parse_datetime(started_at_raw) or cls._started_at,
                'counters': cls._to_int_mapping(counters_raw),
                'failure_reasons': cls._to_int_mapping(failure_reasons_raw),
                'kid_stats': kid_stats,
                'recent_failures': cls._parse_recent_failures(recent_failures_raw),
            }
        except Exception as exc:
            cls._log_redis_warning('read_snapshot', exc)
            return {
                'monitor_scope': 'process-local-fallback',
                'started_at': cls._started_at,
                'counters': {},
                'failure_reasons': {},
                'kid_stats': [],
                'recent_failures': [],
            }

    @classmethod
    async def _get_redis_kid_stats(cls, redis: aioredis.Redis, kids: list[str]) -> list[dict[str, Any]]:
        """
        获取Redis中的按密钥版本聚合统计

        :param redis: Redis客户端
        :param kids: 密钥版本列表
        :return: 按密钥版本统计列表
        """
        if not kids:
            return []
        async with redis.pipeline(transaction=False) as pipe:
            for kid in kids:
                pipe.hgetall(cls._build_kid_counter_key(kid))
            kid_counter_rows = await pipe.execute()
        return [
            {
                'kid': kid,
                'encryptedRequests': cls._to_int_mapping(kid_counter).get('encrypted_requests_total', 0),
                'decryptSuccess': cls._to_int_mapping(kid_counter).get('decrypt_success_total', 0),
                'decryptFailure': cls._to_int_mapping(kid_counter).get('decrypt_failure_total', 0),
                'encryptedResponses': cls._to_int_mapping(kid_counter).get('encrypted_responses_total', 0),
            }
            for kid, kid_counter in zip(kids, kid_counter_rows, strict=False)
        ]

    # 进程内回退统计
    @classmethod
    def _record_plain_request_local(cls) -> None:
        """
        在本地内存中记录明文请求

        :return: None
        """
        with cls._lock:
            cls._counters['requests_total'] += 1
            cls._counters['plain_requests_total'] += 1

    @classmethod
    def _record_encrypted_request_local(cls, kid: str | None = None) -> None:
        """
        在本地内存中记录加密请求

        :param kid: 当前请求使用的密钥版本
        :return: None
        """
        with cls._lock:
            cls._counters['requests_total'] += 1
            cls._counters['encrypted_requests_total'] += 1
            cls._increase_kid_counter_local(kid, 'encrypted_requests_total')

    @classmethod
    def _record_decrypt_success_local(cls, kid: str | None = None) -> None:
        """
        在本地内存中记录解密成功事件

        :param kid: 当前请求使用的密钥版本
        :return: None
        """
        with cls._lock:
            cls._counters['decrypt_success_total'] += 1
            cls._increase_kid_counter_local(kid, 'decrypt_success_total')

    @classmethod
    def _record_plain_response_local(cls) -> None:
        """
        在本地内存中记录明文响应

        :return: None
        """
        with cls._lock:
            cls._counters['plain_responses_total'] += 1

    @classmethod
    def _record_encrypted_response_local(cls, kid: str | None = None, is_error: bool = False) -> None:
        """
        在本地内存中记录加密响应

        :param kid: 当前请求使用的密钥版本
        :param is_error: 是否为错误响应
        :return: None
        """
        with cls._lock:
            cls._counters['encrypted_responses_total'] += 1
            if is_error:
                cls._counters['encrypted_error_responses_total'] += 1
            cls._increase_kid_counter_local(kid, 'encrypted_responses_total')

    @classmethod
    def _record_failure_local(
        cls,
        method: str,
        path: str,
        reason: str,
        kid: str | None = None,
        include_decrypt_failure: bool = True,
    ) -> None:
        """
        在本地内存中记录失败事件

        :param method: 请求方法
        :param path: 请求路径
        :param reason: 失败原因分类
        :param kid: 当前请求使用的密钥版本
        :param include_decrypt_failure: 是否计入解密失败次数
        :return: None
        """
        with cls._lock:
            if include_decrypt_failure:
                cls._counters['decrypt_failure_total'] += 1
            if reason == 'required_missing':
                cls._counters['required_rejected_total'] += 1
            cls._failure_reasons[reason] += 1
            cls._increase_kid_counter_local(kid, 'decrypt_failure_total')
            cls._recent_failures.appendleft(
                {
                    'time': datetime.now(),
                    'method': method,
                    'path': path,
                    'reason': reason,
                    'kid': kid,
                }
            )

    @classmethod
    def _get_local_snapshot_parts(cls) -> dict[str, Any]:
        """
        获取本地内存中的监控快照片段

        :return: 本地监控快照片段
        """
        with cls._lock:
            return {
                'monitor_scope': 'process-local-fallback',
                'started_at': cls._started_at,
                'counters': dict(cls._counters),
                'failure_reasons': dict(cls._failure_reasons),
                'kid_stats': [
                    {
                        'kid': kid,
                        'encryptedRequests': kid_counter.get('encrypted_requests_total', 0),
                        'decryptSuccess': kid_counter.get('decrypt_success_total', 0),
                        'decryptFailure': kid_counter.get('decrypt_failure_total', 0),
                        'encryptedResponses': kid_counter.get('encrypted_responses_total', 0),
                    }
                    for kid, kid_counter in sorted(cls._kid_counters.items(), key=lambda item: item[0])
                ],
                'recent_failures': list(cls._recent_failures),
            }

    @classmethod
    def _merge_snapshot_parts(cls, redis_snapshot: dict[str, Any], local_snapshot: dict[str, Any]) -> dict[str, Any]:
        """
        合并Redis统计与本地回退统计

        :param redis_snapshot: Redis监控快照片段
        :param local_snapshot: 本地监控快照片段
        :return: 合并后的监控快照片段
        """
        merged_counters = Counter(redis_snapshot['counters'])
        merged_counters.update(local_snapshot['counters'])

        merged_failure_reasons = Counter(redis_snapshot['failure_reasons'])
        merged_failure_reasons.update(local_snapshot['failure_reasons'])

        merged_kid_stats: dict[str, dict[str, Any]] = {}
        for kid_stat in redis_snapshot['kid_stats'] + local_snapshot['kid_stats']:
            kid = kid_stat.get('kid')
            if not kid:
                continue
            merged_kid_stat = merged_kid_stats.setdefault(
                kid,
                {
                    'kid': kid,
                    'encryptedRequests': 0,
                    'decryptSuccess': 0,
                    'decryptFailure': 0,
                    'encryptedResponses': 0,
                },
            )
            merged_kid_stat['encryptedRequests'] += int(kid_stat.get('encryptedRequests', 0) or 0)
            merged_kid_stat['decryptSuccess'] += int(kid_stat.get('decryptSuccess', 0) or 0)
            merged_kid_stat['decryptFailure'] += int(kid_stat.get('decryptFailure', 0) or 0)
            merged_kid_stat['encryptedResponses'] += int(kid_stat.get('encryptedResponses', 0) or 0)

        combined_failures = redis_snapshot['recent_failures'] + local_snapshot['recent_failures']
        combined_failures.sort(
            key=lambda item: cls._coerce_datetime_for_sort(item.get('time')),
            reverse=True,
        )

        monitor_scope = redis_snapshot['monitor_scope']
        if monitor_scope == 'redis-aggregated' and cls._has_local_fallback_data(local_snapshot):
            monitor_scope = 'redis-aggregated+local-fallback'

        return {
            'monitor_scope': monitor_scope,
            'started_at': min(redis_snapshot['started_at'], local_snapshot['started_at']),
            'counters': dict(merged_counters),
            'failure_reasons': dict(merged_failure_reasons),
            'kid_stats': sorted(merged_kid_stats.values(), key=lambda item: item['kid']),
            'recent_failures': combined_failures[: cls._RECENT_FAILURE_LIMIT],
        }

    # 快照构建与通用辅助
    @classmethod
    def _build_snapshot(cls, snapshot_parts: dict[str, Any]) -> dict[str, Any]:
        """
        基于监控片段构建最终快照

        :param snapshot_parts: 监控快照片段
        :return: 最终监控快照
        """
        try:
            current_kid = TransportKeyProvider.get_current_kid()
            supported_kids = TransportKeyProvider.get_supported_kids()
        except Exception:
            current_kid = ''
            supported_kids = []

        counters = snapshot_parts['counters']
        return {
            'monitorScope': snapshot_parts['monitor_scope'],
            'startedAt': snapshot_parts['started_at'],
            'appEnv': AppConfig.app_env,
            'transportCryptoEnabled': TransportCryptoConfig.transport_crypto_enabled,
            'transportCryptoMode': TransportCryptoConfig.transport_crypto_mode,
            'currentKid': current_kid,
            'supportedKids': supported_kids,
            'enabledPaths': TransportCryptoUtil._split_paths(TransportCryptoConfig.transport_crypto_enabled_paths),
            'requiredPaths': TransportCryptoUtil._split_paths(TransportCryptoConfig.transport_crypto_required_paths),
            'excludePaths': TransportCryptoUtil._split_paths(TransportCryptoConfig.transport_crypto_exclude_paths),
            'requestsTotal': counters.get('requests_total', 0),
            'plainRequestsTotal': counters.get('plain_requests_total', 0),
            'encryptedRequestsTotal': counters.get('encrypted_requests_total', 0),
            'requiredRejectedTotal': counters.get('required_rejected_total', 0),
            'decryptSuccessTotal': counters.get('decrypt_success_total', 0),
            'decryptFailureTotal': counters.get('decrypt_failure_total', 0),
            'plainResponsesTotal': counters.get('plain_responses_total', 0),
            'encryptedResponsesTotal': counters.get('encrypted_responses_total', 0),
            'encryptedErrorResponsesTotal': counters.get('encrypted_error_responses_total', 0),
            'failureReasons': snapshot_parts['failure_reasons'],
            'kidStats': snapshot_parts['kid_stats'],
            'recentFailures': snapshot_parts['recent_failures'],
        }

    @classmethod
    def _get_redis_client(cls, app: FastAPI | None) -> aioredis.Redis | None:
        """
        获取当前应用中的Redis客户端

        :param app: FastAPI应用对象
        :return: Redis客户端，不存在时返回None
        """
        if app is None:
            return None
        return getattr(app.state, 'redis', None)

    @classmethod
    def _increase_kid_counter_local(cls, kid: str | None, counter_name: str) -> None:
        """
        在本地内存中按密钥版本累加统计值

        :param kid: 当前密钥版本
        :param counter_name: 统计项名称
        :return: None
        """
        if not kid:
            return
        cls._kid_counters[kid][counter_name] += 1

    @classmethod
    def _log_redis_warning(cls, action: str, exc: Exception) -> None:
        """
        记录Redis监控降级日志，并限制日志频率

        :param action: 当前执行动作
        :param exc: 异常对象
        :return: None
        """
        now = time.monotonic()
        with cls._lock:
            if now - cls._last_redis_warning_at < cls._REDIS_WARNING_INTERVAL_SECONDS:
                return
            cls._last_redis_warning_at = now
        logger.warning('传输层加解密监控Redis操作失败，已回退为进程内统计，action={}, error={}', action, exc)

    @classmethod
    def _has_local_fallback_data(cls, local_snapshot: dict[str, Any]) -> bool:
        """
        判断本地回退统计中是否存在有效数据

        :param local_snapshot: 本地监控快照片段
        :return: 是否存在有效数据
        """
        if local_snapshot['counters']:
            return True
        if local_snapshot['failure_reasons']:
            return True
        if local_snapshot['kid_stats']:
            return True
        return bool(local_snapshot['recent_failures'])

    @classmethod
    def _build_kid_counter_key(cls, kid: str) -> str:
        """
        构建按密钥版本统计的Redis键名

        :param kid: 密钥版本
        :return: Redis键名
        """
        return f'{cls._REDIS_KEY_PREFIX}:kid:{kid}:counters'

    @classmethod
    def _parse_recent_failures(cls, recent_failures: list[str]) -> list[dict[str, Any]]:
        """
        解析Redis中的最近失败记录

        :param recent_failures: Redis中存储的失败记录列表
        :return: 失败记录对象列表
        """
        parsed_failures: list[dict[str, Any]] = []
        for recent_failure in recent_failures:
            try:
                recent_failure_item = json.loads(recent_failure)
            except json.JSONDecodeError:
                continue
            if not isinstance(recent_failure_item, dict):
                continue
            recent_failure_item['time'] = cls._parse_datetime(recent_failure_item.get('time'))
            parsed_failures.append(recent_failure_item)
        return parsed_failures

    @staticmethod
    def _to_int_mapping(mapping: dict[str, Any]) -> dict[str, int]:
        """
        将Redis返回的字符串字典转换为整数字典

        :param mapping: Redis原始字典
        :return: 转换后的整数字典
        """
        return {str(key): int(value) for key, value in mapping.items()}

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """
        将字符串时间解析为datetime对象

        :param value: 原始时间值
        :return: datetime对象，解析失败时返回None
        """
        if isinstance(value, datetime):
            return value
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @classmethod
    def _coerce_datetime_for_sort(cls, value: Any) -> datetime:
        """
        将任意时间值转换为可排序的datetime对象

        :param value: 原始时间值
        :return: datetime对象
        """
        parsed_datetime = cls._parse_datetime(value)
        if parsed_datetime:
            return parsed_datetime
        return datetime.min
