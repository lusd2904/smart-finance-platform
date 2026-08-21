import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.env import AppSettings
from module_analysis.service.analysis_job_service import AnalysisJobService
from module_task.analysis_catalog import ANALYSIS_JOB_MAP, ANALYSIS_JOBS, humanize_cron
from utils.scheduler_runtime import SchedulerRuntime


def test_role_helpers_isolate_api_from_scheduler() -> None:
    api = AppSettings(app_role='api', app_job_group='none')
    scheduler = AppSettings(app_role='scheduler', app_job_group='none')
    worker = AppSettings(app_role='worker', app_job_group='market')
    both = AppSettings(app_role='all')
    assert not api.runs_scheduler()
    assert not api.runs_job_queue_worker()
    assert scheduler.runs_scheduler()
    assert not scheduler.runs_job_queue_worker()
    assert not worker.runs_scheduler()
    assert worker.runs_job_queue_worker()
    assert both.runs_scheduler()
    assert both.runs_job_queue_worker()
    assert AppSettings(app_module='trade').router_modules() == {'module_trade'}
    assert AppSettings(app_module='all').router_modules() is None


def test_catalog_job_ids_unique_and_targets_exist() -> None:
    ids = [item.job_id for item in ANALYSIS_JOBS]
    assert len(ids) == len(set(ids))
    assert set(ANALYSIS_JOB_MAP) == set(ids)
    for spec in ANALYSIS_JOBS:
        module_path, func_name = spec.invoke_target.rsplit('.', 1)
        module = importlib.import_module(module_path)
        assert callable(getattr(module, func_name)), spec.invoke_target


def test_humanize_cron_known_schedules() -> None:
    assert humanize_cron('0 0/10 * * * ?') == '每 10 分钟'
    assert humanize_cron('0 30 5 * * ?') == '每天 05:30'
    assert humanize_cron('0 15 * * * ?') == '每小时第 15 分钟'
    assert humanize_cron('0 0/30 * * * ?') == '每 30 分钟'
    assert humanize_cron('0 5/15 * * * ?') == '每 15 分钟（从第 5 分钟）'
    assert humanize_cron('') == '--'


def test_heartbeat_alive_helper() -> None:
    assert SchedulerRuntime.is_alive({'alive': True})
    assert not SchedulerRuntime.is_alive(None)
    assert not SchedulerRuntime.is_alive({})


def test_auto_trade_uses_free_job_id() -> None:
    assert ANALYSIS_JOB_MAP[112].code == 'auto_trade_scan'


def test_extra_jobs_are_treated_as_analysis_targets() -> None:
    assert AnalysisJobService._is_analysis_target('module_task.market_task.analyze_market_review_job')
    assert AnalysisJobService._category_from_target('module_task.market_task.analyze_market_review_job') == 'market'
    assert not AnalysisJobService._is_analysis_target('module_task.scheduler_test.job')
