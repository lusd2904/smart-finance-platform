"""Scheduler ORM row → JobModel must keep snake_case invoke_target."""

import os
import sys
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.providers import ModuleAdminSchedulerJobPersistence


def test_build_job_from_row_keeps_snake_case_invoke_target() -> None:
    invoke_target = 'module_task.scheduler_test.job'
    row = SimpleNamespace(
        job_id=1,
        job_name='scheduler test',
        invoke_target=invoke_target,
        status='0',
        cron_expression='0/10 * * * * ?',
    )
    job = ModuleAdminSchedulerJobPersistence().build_job_from_row(row)
    assert job.invoke_target == invoke_target
