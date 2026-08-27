"""启动后台任务：操作日志流只应由一份进程消费。"""

import os
import sys
from unittest.mock import patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.env import AppConfig
from server import _should_consume_op_logs


def test_op_log_stream_only_on_platform_or_monolith() -> None:
    with patch.object(AppConfig, 'app_role', 'api'), patch.object(AppConfig, 'app_module', 'trade'):
        assert _should_consume_op_logs() is False
    with patch.object(AppConfig, 'app_role', 'api'), patch.object(AppConfig, 'app_module', 'market'):
        assert _should_consume_op_logs() is False
    with patch.object(AppConfig, 'app_role', 'api'), patch.object(AppConfig, 'app_module', 'platform'):
        assert _should_consume_op_logs() is True
    with patch.object(AppConfig, 'app_role', 'all'), patch.object(AppConfig, 'app_module', 'trade'):
        assert _should_consume_op_logs() is True
