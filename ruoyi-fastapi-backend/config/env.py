import argparse
import configparser
import os
import sys
from typing import Literal

from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """
    应用配置
    """

    app_env: str = 'dev'
    app_name: str = 'RuoYi-FasAPI'
    app_root_path: str = '/dev-api'
    app_host: str = '0.0.0.0'
    app_port: int = 9099
    app_version: str = '1.0.0'
    app_reload: bool = True
    app_workers: int = 1
    app_ip_location_query: bool = True
    app_same_time_login: bool = True
    app_demo_mode: bool = False
    app_disable_swagger: bool = False
    app_disable_redoc: bool = False
    app_trusted_proxy_ips: str = '127.0.0.1,::1'
    app_trusted_proxy_hops: int = 1
    # api=仅 HTTP；scheduler=仅 APScheduler；worker=仅队列消费；all=单进程（本地默认）
    app_role: Literal['api', 'scheduler', 'worker', 'all'] = 'all'
    # none=不消费；market/quant/llm=单一消费组；all=三组都消费
    app_job_group: Literal['none', 'market', 'quant', 'llm', 'all'] = 'all'
    # all=挂全部路由；其余按菜单板块只注册对应模块
    app_module: Literal['all', 'platform', 'market', 'quant', 'trade', 'sentiment', 'ai'] = 'all'
    # 对外需求清单 GET /open/requirements 的 X-Req-Token，空则关闭
    requirements_export_token: str = ''
    # 舆情大盘 Widget GET /sentiment/widget/dashboard 的 X-Widget-Token，空则关闭
    sentiment_widget_token: str = ''
    # CORS 域名白名单，逗号分隔；dev 未配置时放开来源但关闭凭证，prod 必须显式配置
    app_cors_origins: str = ''

    def runs_scheduler(self) -> bool:
        return self.app_role in {'scheduler', 'all'}

    def runs_job_queue_worker(self) -> bool:
        if self.app_job_group == 'none':
            return False
        return self.app_role in {'scheduler', 'worker', 'all'}

    def router_modules(self) -> set[str] | None:
        if self.app_module == 'all':
            return None
        mapping = {
            'platform': {'module_admin', 'module_generator', 'module_analysis'},
            'market': {'module_market'},
            'quant': {'module_quant'},
            'trade': {'module_trade'},
            'sentiment': {'module_sentiment'},
            'ai': {'module_ai'},
        }
        return mapping.get(self.app_module)


# JWT secret 最小长度（对应 256-bit 强度）
JWT_SECRET_MIN_LEN = 32


class JwtSettings(BaseSettings):
    """
    Jwt配置
    """

    # 安全默认：不再内置任何 secret。未显式配置时启动即失败，避免使用公开模板值被伪造 token。
    jwt_secret_key: str = ''
    # 库内敏感数据（券商凭据等）加密密钥，与 JWT secret 独立以便单独轮换；未配置时回退 JWT secret（生产强制要求独立配置）
    credential_encryption_key: str = ''
    jwt_algorithm: str = 'HS256'
    # token 有效期从 24h 收紧到 8h；Redis 会话仍随请求滑动续期
    jwt_expire_minutes: int = 480
    jwt_redis_expire_minutes: int = 30

    def validate_security(self) -> None:
        """
        启动安全校验：secret 缺失或仍为历史公开模板值时拒绝启动。

        :return: None
        """
        insecure_values = {
            'b01c66dc2c58dc6a0aabfe2144256be36226de378bf87f72c0c795dda67f4d55',
            'CHANGE_ME_RANDOM_HEX',
        }
        key = (self.jwt_secret_key or '').strip()
        if not key:
            raise RuntimeError(
                '安全检查失败：JWT_SECRET_KEY 未配置。请在 .env 文件中设置随机强密钥'
                '（可用 `openssl rand -hex 32` 生成），禁止使用公开模板默认值。'
            )
        if key.lower() in insecure_values or len(key) < JWT_SECRET_MIN_LEN:
            raise RuntimeError(
                '安全检查失败：JWT_SECRET_KEY 为公开模板值或强度不足（<32 字符），请更换为随机强密钥。'
            )


class DataBaseSettings(BaseSettings):
    """
    数据库配置
    """

    db_type: Literal['mysql', 'postgresql'] = 'mysql'
    db_host: str = '127.0.0.1'
    db_port: int = 3306
    db_username: str = 'root'
    db_password: str = 'mysqlroot'
    db_database: str = 'ruoyi-fastapi'
    db_echo: bool = True
    # 池上限需与 MySQL max_connections 联动：API+调度双引擎同进程时理论峰值 = 2*(pool_size+overflow)，
    # 默认 20+10 已按 compose 中 max-connections=300 预留余量
    db_max_overflow: int = 10
    db_pool_size: int = 20
    db_pool_recycle: int = 3600
    db_pool_timeout: int = 30

    @computed_field
    @property
    def sqlglot_parse_dialect(self) -> str:
        if self.db_type == 'postgresql':
            return 'postgres'
        return self.db_type


class RedisSettings(BaseSettings):
    """
    Redis配置
    """

    redis_host: str = '127.0.0.1'
    redis_port: int = 6379
    redis_username: str = ''
    redis_password: str = ''
    redis_database: int = 2


class InfluxSettings(BaseSettings):
    """
    InfluxDB时序数据库配置（行情/量化数据）
    """

    influx_url: str = 'http://127.0.0.1:8086'
    influx_token: str = ''
    influx_org: str = 'longbridge'
    influx_bucket_us: str = 'market_us'
    influx_bucket_cn: str = 'market_data'


class KlineSettings(BaseSettings):
    """
    行情K线同步配置（module_market 同步任务）
    """

    # 全市场慢速同步单个标的间隔（秒）
    kline_symbol_interval: float = 1.5
    # 本地日K条数达到该值才允许跳过外网补源
    kline_skip_min_bars: int = 200
    # 本地最新日K距今不超过该天数才跳过外网补源
    kline_skip_fresh_days: int = 10


class LongbridgeSettings(BaseSettings):
    """
    长桥证券SDK配置（量化交易接入）
    """

    longport_app_key: str = ''
    longport_app_secret: str = ''
    longport_access_token: str = ''
    longport_region: str = 'cn'
    longport_trading_enabled: bool = False


class LogSettings(BaseSettings):
    """
    日志与队列配置
    """

    log_mask_enabled: bool = True
    log_mask_placeholder: str = '******'
    log_mask_fields: str = (
        'password,old_password,new_password,confirm_password,api_key,token,access_token,refresh_token,'
        'authorization,client_secret,secret,secret_key,private_key,private_key_pem,credential,credentials,'
        'sms_code,captcha_code,system_prompt'
    )
    log_partial_mask_fields: str = 'phonenumber,phone,mobile,email'
    log_config_secret_patterns: str = 'password,token,secret,key,private,credential,access,jwt,captcha,sms'
    log_stream_key: str = 'log:stream'
    log_stream_group: str = 'log_aggregator'
    log_stream_consumer_prefix: str = 'worker'
    log_stream_batch_size: int = 100
    log_stream_block_ms: int = 2000
    log_stream_maxlen: int = 100000
    log_stream_claim_idle_ms: int = 60000
    log_stream_claim_interval_ms: int = 5000
    log_stream_claim_batch_size: int = 100
    log_stream_dedup_ttl: int = 3600
    log_stream_dedup_prefix: str = 'log:dedup'

    loguru_json: bool = False
    loguru_level: str = 'INFO'
    loguru_stdout: bool = True
    log_file_enabled: bool = True
    log_file_base_dir: str = 'logs'
    loguru_rotation: str = '50MB'
    loguru_retention: str = '30 days'
    loguru_compression: str = 'zip'
    log_instance_id: str = 'prod'
    log_service_name: str = 'ruoyi-fastapi-backend'
    log_worker_id: str = 'auto'


class TransportCryptoSettings(BaseSettings):
    """
    传输层加解密配置
    """

    transport_crypto_enabled: bool = True
    transport_crypto_mode: Literal['off', 'optional', 'required'] = 'optional'
    transport_crypto_algorithm: str = 'RSA_OAEP_AES_256_GCM'
    transport_crypto_kid: str = 'default'
    transport_crypto_public_key: str = ''
    transport_crypto_private_key: str = ''
    transport_crypto_legacy_key_pairs: str = '[]'
    transport_crypto_rsa_key_size: int = 2048
    transport_crypto_public_key_ttl_seconds: int = 3600
    transport_crypto_frontend_config_ttl_seconds: int = 300
    transport_crypto_max_get_url_length: int = 4096
    transport_crypto_clock_skew_seconds: int = 120
    transport_crypto_replay_ttl_seconds: int = 300
    transport_crypto_enabled_paths: str = ''
    transport_crypto_required_paths: str = ''
    transport_crypto_exclude_paths: str = (
        '/openapi.json,/docs,/docs/oauth2-redirect,/redoc,'
        '/transport/crypto/frontend-config,/transport/crypto/public-key,/common/download,/common/download/resource'
    )


class GenSettings:
    """
    代码生成配置
    """

    author = 'insistence'
    package_name = 'module_admin.system'
    auto_remove_pre = False
    table_prefix = 'sys_'
    allow_overwrite = False

    GEN_PATH = 'vf_admin/gen_path'

    def __init__(self) -> None:
        if not os.path.exists(self.GEN_PATH):
            os.makedirs(self.GEN_PATH)


class UploadSettings:
    """
    上传配置
    """

    UPLOAD_PREFIX = '/profile'
    UPLOAD_PATH = 'vf_admin/upload_path'
    UPLOAD_MACHINE = 'A'
    DEFAULT_ALLOWED_EXTENSION = [
        # 图片
        'bmp',
        'gif',
        'jpg',
        'jpeg',
        'png',
        # word excel powerpoint
        'doc',
        'docx',
        'xls',
        'xlsx',
        'ppt',
        'pptx',
        'html',
        'htm',
        'txt',
        # 压缩文件
        'rar',
        'zip',
        'gz',
        'bz2',
        # 视频格式
        'mp4',
        'avi',
        'rmvb',
        # pdf
        'pdf',
    ]
    DOWNLOAD_PATH = 'vf_admin/download_path'

    def __init__(self) -> None:
        if not os.path.exists(self.UPLOAD_PATH):
            os.makedirs(self.UPLOAD_PATH)
        if not os.path.exists(self.DOWNLOAD_PATH):
            os.makedirs(self.DOWNLOAD_PATH)


class CachePathConfig:
    """
    缓存目录配置
    """

    PATH = os.path.join(os.path.abspath(os.getcwd()), 'caches')
    PATHSTR = 'caches'


class GetConfig:
    """
    获取配置
    """

    def __init__(self) -> None:
        self.parse_cli_args()

    def get_app_config(self) -> AppSettings:
        """
        获取应用配置
        """
        # 实例化应用配置模型
        return AppSettings()

    def get_jwt_config(self) -> JwtSettings:
        """
        获取Jwt配置
        """
        # 实例化Jwt配置模型并执行启动安全校验
        jwt_config = JwtSettings()
        jwt_config.validate_security()
        return jwt_config

    def get_database_config(self) -> DataBaseSettings:
        """
        获取数据库配置
        """
        # 实例化数据库配置模型
        return DataBaseSettings()

    def get_redis_config(self) -> RedisSettings:
        """
        获取Redis配置
        """
        # 实例化Redis配置模型
        return RedisSettings()

    def get_log_config(self) -> LogSettings:
        """
        获取日志配置
        """
        return LogSettings()

    def get_influx_config(self) -> InfluxSettings:
        """
        获取InfluxDB时序数据库配置
        """
        return InfluxSettings()

    def get_longbridge_config(self) -> LongbridgeSettings:
        """
        获取长桥证券SDK配置
        """
        return LongbridgeSettings()

    def get_kline_config(self) -> KlineSettings:
        """
        获取行情K线同步配置
        """
        return KlineSettings()

    def get_transport_crypto_config(self) -> TransportCryptoSettings:
        """
        获取传输层加解密配置
        """
        return TransportCryptoSettings()

    def get_gen_config(self) -> GenSettings:
        """
        获取代码生成配置
        """
        # 实例化代码生成配置
        return GenSettings()

    def get_upload_config(self) -> UploadSettings:
        """
        获取上传配置
        """
        # 实例上传配置
        return UploadSettings()

    @staticmethod
    def parse_cli_args() -> None:
        """
        解析命令行参数
        """
        # 检查是否在alembic环境中运行，如果是则跳过参数解析
        if 'alembic' in sys.argv[0] or any('alembic' in arg for arg in sys.argv):
            ini_config = configparser.ConfigParser()
            ini_config.read('alembic.ini', encoding='utf-8')
            if 'settings' in ini_config:
                # 获取env选项
                env_value = ini_config['settings'].get('env')
                os.environ['APP_ENV'] = env_value if env_value else 'dev'
        elif 'uvicorn' in sys.argv[0]:
            # 使用uvicorn启动时，命令行参数需要按照uvicorn的文档进行配置，无法自定义参数
            pass
        else:
            # 使用argparse定义命令行参数
            parser = argparse.ArgumentParser(description='命令行参数')
            parser.add_argument('--env', type=str, default='', help='运行环境')
            # 解析命令行参数
            args, _ = parser.parse_known_args()
            # 设置环境变量，如果未设置命令行参数，默认APP_ENV为dev
            os.environ['APP_ENV'] = args.env if args.env else 'dev'
        # 读取运行环境
        run_env = os.environ.get('APP_ENV', '')
        # 运行环境未指定时默认加载.env.dev
        env_file = '.env.dev'
        # 运行环境不为空时按命令行参数加载对应.env文件
        if run_env != '':
            env_file = f'.env.{run_env}'
        # 加载配置
        load_dotenv(env_file)


# 实例化获取配置类
get_config = GetConfig()
# 应用配置
AppConfig = get_config.get_app_config()
# Jwt配置
JwtConfig = get_config.get_jwt_config()
# 数据库配置
DataBaseConfig = get_config.get_database_config()
# Redis配置
RedisConfig = get_config.get_redis_config()
# 日志配置
LogConfig = get_config.get_log_config()
# InfluxDB时序数据库配置
InfluxConfig = get_config.get_influx_config()
# 长桥证券SDK配置
LongbridgeConfig = get_config.get_longbridge_config()
# 传输层加解密配置
TransportCryptoConfig = get_config.get_transport_crypto_config()
# 代码生成配置
GenConfig = get_config.get_gen_config()
# 上传配置
UploadConfig = get_config.get_upload_config()
