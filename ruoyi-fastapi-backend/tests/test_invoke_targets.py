"""Go invoke_target mapping: catalog, SQL migration, and admin whitelist."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_admin.service.job_service import JobService
from module_task.analysis_catalog import ANALYSIS_JOBS
from module_task.invoke_targets import (
    GO_JOB_CATEGORY,
    GO_JOB_KEYS,
    PYTHON_INVOKE_ALIASES,
    is_allowed_job_invoke_target,
    is_analysis_invoke_target,
    is_go_invoke_target,
)

REPO = Path(__file__).resolve().parents[2]
SQL_INCREMENTAL = REPO / 'ruoyi-fastapi-backend' / 'sql' / 'sys-job-go-invoke-targets.sql'
SQL_OPERATOR = REPO / 'scripts' / 'migrate_sys_job_go_invoke_targets.sql'

# Live-shaped inventory: ~23 analysis rows still on module_task.*, plus demo + already-Go.
LIVE_LIKE_ROWS = [
    (1, 'module_task.scheduler_test.job', None, '1'),
    (100, 'module_task.sentiment_task.collect_and_analyze_job', None, '0'),
    (101, 'module_task.market_task.sync_market_job', None, '0'),
    (102, 'module_task.quant_task.run_strategy_job', None, '1'),
    (103, 'finance_briefings', None, '0'),
    (104, 'module_task.market_task.refresh_symbol_content_job', None, '0'),
    (105, 'module_task.quant_task.run_daily_factor_scan_job', None, '1'),
    (106, 'module_task.quant_task.run_position_monitor_job', None, '0'),
    (107, 'indicator_refresh', None, '0'),
    (108, 'module_task.quant_task.run_factor_qc_job', None, '1'),
    (109, 'module_task.market_task.analyze_watchlist_job', None, '0'),
    (110, 'module_task.market_task.analyze_market_review_job', None, '0'),
    (111, 'module_task.market_task.analyze_market_review_job', None, '0'),
    (112, 'module_task.trade_task.run_auto_trade_scan_job', None, '1'),
    (113, 'module_task.market_task.collect_market_heat_cn_job', None, '0'),
    (114, 'module_task.market_task.collect_market_heat_hk_job', None, '0'),
    (115, 'module_task.market_task.collect_market_heat_us_job', None, '0'),
    (116, 'module_task.quant_task.run_daily_list_scan_job', None, '0'),
    (117, 'feishu_push', None, '0'),
    (118, 'module_task.quant_task.run_daily_list_open_job', None, '0'),
    (119, 'module_task.market_task.run_stock_pick_job', None, '0'),
    (121, 'module_task.market_task.eod_kline_sync_cn_job', None, '0'),
    (122, 'module_task.market_task.eod_kline_sync_hk_job', None, '0'),
    (123, 'module_task.market_task.eod_kline_sync_us_job', None, '0'),
]


def _apply_mapping(rows: list[tuple[int, str, str | None, str]]) -> list[tuple[int, str, str | None, str]]:
    out = []
    for job_id, target, kwargs, status in rows:
        mapped = PYTHON_INVOKE_ALIASES.get(target)
        if not mapped:
            out.append((job_id, target, kwargs, status))
            continue
        go_key, default_kwargs = mapped
        next_kwargs = kwargs
        if default_kwargs and (kwargs is None or str(kwargs).strip() in ('', '{}')):
            next_kwargs = default_kwargs
        out.append((job_id, go_key, next_kwargs, status))
    return out


def test_go_keys_cover_catalog_and_categories() -> None:
    assert GO_JOB_KEYS == frozenset(GO_JOB_CATEGORY)
    for spec in ANALYSIS_JOBS:
        assert spec.invoke_target in GO_JOB_KEYS
        assert GO_JOB_CATEGORY[spec.invoke_target] in {'market', 'quant', 'sentiment', 'trade'}


def test_sql_mentions_every_python_alias() -> None:
    incremental = SQL_INCREMENTAL.read_text(encoding='utf-8')
    operator = SQL_OPERATOR.read_text(encoding='utf-8')
    for python_target in PYTHON_INVOKE_ALIASES:
        assert python_target in incremental, python_target
        assert python_target in operator, python_target
    assert "module_task.scheduler_test.job" not in re.sub(
        r'--.*', '', incremental
    )


def test_live_like_before_after_counts() -> None:
    def python_analysis(rows: list[tuple[int, str, str | None, str]]) -> int:
        return sum(
            1
            for _, target, _, _ in rows
            if target.startswith('module_task.') and 'scheduler_test' not in target
        )

    before = python_analysis(LIVE_LIKE_ROWS)
    after_rows = _apply_mapping(LIVE_LIKE_ROWS)
    after = python_analysis(after_rows)
    enabled_go = [
        (job_id, target, kwargs)
        for job_id, target, kwargs, status in after_rows
        if status == '0' and job_id != 1
    ]
    assert before == 20, before
    assert after == 0, after_rows
    assert all(is_go_invoke_target(target) for _, target, _ in enabled_go)
    heat = {job_id: kwargs for job_id, target, kwargs, _ in after_rows if target == 'market_heat_collect'}
    assert heat[113] == '{"market":"CN"}'
    assert heat[114] == '{"market":"HK"}'
    assert heat[115] == '{"market":"US"}'
    eod = {job_id: kwargs for job_id, target, kwargs, _ in after_rows if target == 'eod_kline_sync'}
    assert eod[121] == '{"market":"CN"}'
    assert eod[122] == '{"market":"HK"}'
    assert eod[123] == '{"market":"US"}'
    # Second apply is a no-op.
    assert _apply_mapping(after_rows) == after_rows


def test_admin_whitelist_accepts_go_keys() -> None:
    assert is_allowed_job_invoke_target('module_task.market_task.sync_market_job')
    assert is_allowed_job_invoke_target('finance_briefings')
    assert JobService._is_go_invoke_target('indicator_refresh')
    assert not is_allowed_job_invoke_target('os.system')
    assert not is_allowed_job_invoke_target('not_a_job')
    assert is_analysis_invoke_target('eod_kline_sync')
    assert not is_analysis_invoke_target('module_task.scheduler_test.job')
