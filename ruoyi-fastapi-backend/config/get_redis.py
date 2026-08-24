from fastapi import FastAPI
from redis import asyncio as aioredis
from redis.exceptions import AuthenticationError, RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from config.env import RedisConfig
from config.providers import get_cache_warm_provider
from utils.log_util import logger


class RedisUtil:
    """
    Redis相关方法
    """

    _client: aioredis.Redis | None = None

    @classmethod
    def get_client(cls) -> aioredis.Redis | None:
        """返回进程内 Redis 连接，启动前或关闭后为 None。"""
        return cls._client

    @classmethod
    async def create_redis_pool(cls, log_enabled: bool = True, log_start_enabled: bool | None = None) -> aioredis.Redis:
        """
        应用启动时初始化redis连接

        :param log_enabled: 是否输出日志
        :param log_start_enabled: 是否输出开始连接日志
        :return: Redis连接对象
        """
        redis = await aioredis.from_url(
            url=f'redis://{RedisConfig.redis_host}',
            port=RedisConfig.redis_port,
            username=RedisConfig.redis_username,
            password=RedisConfig.redis_password,
            db=RedisConfig.redis_database,
            encoding='utf-8',
            decode_responses=True,
        )
        if log_start_enabled is None:
            log_start_enabled = log_enabled
        if log_enabled or log_start_enabled:
            await cls.check_redis_connection(redis, log_enabled=log_enabled, log_start_enabled=log_start_enabled)
        cls._client = redis
        return redis

    @classmethod
    async def check_redis_connection(
        cls, redis: aioredis.Redis, log_enabled: bool = True, log_start_enabled: bool | None = None
    ) -> None:
        """
        检查redis连接状态

        :param redis: redis对象
        :param log_enabled: 是否输出日志
        :param log_start_enabled: 是否输出开始连接日志
        :return: None
        """
        if log_start_enabled is None:
            log_start_enabled = log_enabled
        if log_start_enabled:
            logger.info('🔎 开始连接redis...')
        try:
            connection = await redis.ping()
            if not log_enabled:
                return
            if connection:
                logger.info('✅️ redis连接成功')
            else:
                logger.error('❌️ redis连接失败')
        except AuthenticationError as e:
            if log_enabled:
                logger.error(f'❌️ redis用户名或密码错误，详细错误信息：{e}')
        except RedisTimeoutError as e:
            if log_enabled:
                logger.error(f'❌️ redis连接超时，详细错误信息：{e}')
        except RedisError as e:
            if log_enabled:
                logger.error(f'❌️ redis连接错误，详细错误信息：{e}')

    @classmethod
    async def close_redis_pool(cls, app: FastAPI) -> None:
        """
        应用关闭时关闭redis连接

        :param app: fastapi对象
        :return:
        """
        await app.state.redis.close()
        cls._client = None
        logger.info('✅️ 关闭redis连接成功')

    @classmethod
    async def init_sys_dict(cls, redis: aioredis.Redis) -> None:
        """
        应用启动时缓存字典表（实现由 config.providers 装配，公共层不依赖业务模块）

        :param redis: redis对象
        :return:
        """
        await get_cache_warm_provider().warm_dict_cache(redis)

    @classmethod
    async def init_sys_config(cls, redis: aioredis.Redis) -> None:
        """
        应用启动时缓存参数配置表（实现由 config.providers 装配，公共层不依赖业务模块）

        :param redis: redis对象
        :return:
        """
        await get_cache_warm_provider().warm_config_cache(redis)
