"""Slim stack composite APP_MODULE=data|intel (market+quant / sentiment+ai)."""

import glob
import os
import sys
from unittest.mock import patch

import pytest

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI

from common.router import RouterRegister
from config.env import AppConfig, AppSettings
from server import _should_consume_op_logs


@pytest.mark.parametrize(
    ('module', 'expected'),
    [
        ('data', {'module_market', 'module_quant'}),
        ('intel', {'module_sentiment', 'module_ai'}),
        ('market', {'module_market'}),
        ('sentiment', {'module_sentiment'}),
    ],
)
def test_slim_composite_router_modules(module: str, expected: set[str]) -> None:
    assert AppSettings(app_module=module).router_modules() == expected


def test_data_and_intel_are_disjoint_from_trade_and_platform() -> None:
    data = AppSettings(app_module='data').router_modules() or set()
    intel = AppSettings(app_module='intel').router_modules() or set()
    assert 'module_trade' not in data | intel
    assert 'module_admin' not in data | intel
    assert data.isdisjoint(intel)


def test_slim_api_roles_do_not_run_scheduler_or_queue() -> None:
    for module in ('data', 'intel'):
        cfg = AppSettings(app_role='api', app_module=module, app_job_group='none')
        assert not cfg.runs_scheduler()
        assert not cfg.runs_job_queue_worker()


def test_slim_jobs_scheduler_consumes_all_groups() -> None:
    cfg = AppSettings(app_role='scheduler', app_module='platform', app_job_group='all')
    assert cfg.runs_scheduler()
    assert cfg.runs_job_queue_worker()


@pytest.mark.parametrize('module', ['data', 'intel', 'market', 'sentiment', 'ai'])
def test_op_log_stream_not_on_slim_data_or_intel_api(module: str) -> None:
    with patch.object(AppConfig, 'app_role', 'api'), patch.object(AppConfig, 'app_module', module):
        assert _should_consume_op_logs() is False


def test_router_register_finds_only_allowed_controllers_for_data() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    allowed = AppSettings(app_module='data').router_modules()
    assert allowed is not None
    files: list[str] = []
    for module_name in sorted(allowed):
        pattern = os.path.join(project_root, module_name, 'controller', '[!_]*.py')
        files.extend(glob.glob(pattern))
    assert files, 'data module should register at least one controller'
    joined = '\n'.join(files)
    assert 'module_market' in joined
    assert 'module_quant' in joined
    assert 'module_trade' not in joined
    assert 'module_sentiment' not in joined


def test_router_register_finds_only_allowed_controllers_for_intel() -> None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    allowed = AppSettings(app_module='intel').router_modules()
    assert allowed is not None
    files: list[str] = []
    for module_name in sorted(allowed):
        pattern = os.path.join(project_root, module_name, 'controller', '[!_]*.py')
        files.extend(glob.glob(pattern))
    assert files, 'intel module should register at least one controller'
    joined = '\n'.join(files)
    assert 'module_sentiment' in joined
    assert 'module_ai' in joined
    assert 'module_market' not in joined


def test_router_register_class_respects_patched_data_module() -> None:
    with patch('config.env.AppConfig') as mock_cfg:
        mock_cfg.router_modules.return_value = AppSettings(app_module='data').router_modules()
        reg = RouterRegister(FastAPI())
        files = reg._find_controller_files()
    assert files
    blob = '\n'.join(files)
    assert 'module_market' in blob and 'module_quant' in blob
    assert 'module_ai' not in blob
