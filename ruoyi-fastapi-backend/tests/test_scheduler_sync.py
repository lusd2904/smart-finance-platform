"""Scheduler sync: do not treat add/remove as execution; skip no-op updates."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.scheduler.event_listeners import EventListenersMixin
from config.scheduler.job_crud import JobCrudMixin


def test_listener_ignores_job_added_event() -> None:
    class JobEvent:
        job_id = '111'
        exception = None

    EventListenersMixin.scheduler_event_listener(JobEvent())


def test_in_sync_compares_invoke_path_not_func_repr() -> None:
    from config.scheduler.triggers import MyCronTrigger

    job_info = SimpleNamespace(
        job_name='美股收盘市场分析',
        job_executor='default',
        job_group='default',
        misfire_policy='3',
        concurrent='1',
        cron_expression='0 15 5 * * ?',
        job_args='US',
        job_kwargs='{}',
        invoke_target='module_task.market_task.analyze_market_review_job',
    )
    trigger = str(MyCronTrigger.from_crontab(job_info.cron_expression))

    class FakeJob:
        _jobstore_alias = 'default'

        def __getstate__(self):
            return {
                'name': '美股收盘市场分析',
                'executor': 'default',
                'misfire_grace_time': 1000000000000,
                'coalesce': False,
                'max_instances': 1,
                'trigger': trigger,
                'args': ('US',),
                'kwargs': {},
                'func': 'module_task.market_task.analyze_market_review_job',
            }

    assert JobCrudMixin._is_job_config_in_sync(FakeJob(), job_info) is True


def test_skip_update_when_null_timestamp_already_loaded() -> None:
    JobCrudMixin._job_update_time_cache.clear()
    assert JobCrudMixin._should_skip_job_update('111', None) is False
    JobCrudMixin._refresh_job_update_cache('111', None)
    assert JobCrudMixin._should_skip_job_update('111', None) is True
