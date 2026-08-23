"""
传输层安全校验

拆分自 utils/transport_crypto_util.py，负责请求时间窗校验
与基于Redis的防重放校验。
"""

import time

from fastapi import Request

from config.env import AppConfig, TransportCryptoConfig
from utils.log_util import logger


# 传输层安全校验
class TransportSecurityUtil:
    """
    传输层安全校验工具
    """

    @classmethod
    def validate_timestamp(cls, timestamp: int) -> None:
        """
        校验请求时间窗

        :param timestamp: 请求信封中的时间戳
        :return: None
        """
        now_timestamp = int(time.time())
        if abs(now_timestamp - timestamp) > TransportCryptoConfig.transport_crypto_clock_skew_seconds:
            logger.warning(
                '传输层加密请求时间窗校验失败，request_ts={}, now_ts={}, allowed_skew={}',
                timestamp,
                now_timestamp,
                TransportCryptoConfig.transport_crypto_clock_skew_seconds,
            )
            raise ValueError('加密请求已过期，请刷新页面后重试')

    @classmethod
    async def validate_replay(cls, request: Request, kid: str, nonce: str) -> None:
        """
        使用Redis进行防重放校验

        :param request: 当前请求对象
        :param kid: 当前密钥版本标识
        :param nonce: 当前请求随机数
        :return: None
        """
        redis = getattr(request.app.state, 'redis', None)
        if redis is None:
            if cls._should_fail_closed_when_replay_check_unavailable(request):
                logger.error('Redis未初始化，当前请求要求严格防重放校验，已拒绝请求')
                raise ValueError('服务端防重放校验不可用，请稍后重试')
            logger.warning('Redis未初始化，已跳过传输层防重放校验')
            return

        replay_key = f'transport:replay:{kid}:{nonce}'
        try:
            is_success = await redis.set(
                replay_key, '1', ex=TransportCryptoConfig.transport_crypto_replay_ttl_seconds, nx=True
            )
        except Exception as exc:
            if cls._should_fail_closed_when_replay_check_unavailable(request):
                logger.error('Redis防重放校验执行失败，当前请求要求严格校验，error={}', exc)
                raise ValueError('服务端防重放校验不可用，请稍后重试') from exc
            logger.warning('Redis防重放校验执行失败，已跳过当前请求的防重放校验，error={}', exc)
            return
        if not is_success:
            logger.warning('传输层加密请求检测到重放，kid={}, nonce={}', kid, nonce)
            raise ValueError('检测到重复请求，请勿重放加密报文')

    @classmethod
    def _should_fail_closed_when_replay_check_unavailable(cls, request: Request) -> bool:
        """
        判断当前请求在防重放能力不可用时是否需要直接拒绝

        :param request: 当前请求对象
        :return: 是否需要失败关闭
        """
        if TransportCryptoConfig.transport_crypto_mode == 'required':
            return True
        current_path = cls._normalize_path(str(request.scope.get('path', '')))
        return cls._is_required_path(current_path)

    @staticmethod
    def _normalize_path(path: str) -> str:
        """
        标准化请求路径，剥离应用根路径前缀

        :param path: 原始请求路径
        :return: 标准化后的业务路径
        """
        app_root_path = AppConfig.app_root_path
        if app_root_path and path.startswith(app_root_path):
            normalized_path = path[len(app_root_path) :]
            return normalized_path or '/'
        return path or '/'

    @staticmethod
    def _is_required_path(path: str) -> bool:
        """
        判断当前路径是否命中强制加密路径配置

        :param path: 当前请求路径
        :return: 是否命中强制加密路径
        """
        required_paths = [
            required_path.strip()
            for required_path in TransportCryptoConfig.transport_crypto_required_paths.split(',')
            if required_path.strip()
        ]
        if not required_paths:
            return False
        return any(path == required_path or path.startswith(f'{required_path}/') for required_path in required_paths)
