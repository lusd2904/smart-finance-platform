"""Canonical Go sys_job.invoke_target keys and leftover Python aliases.

After the SQL migration, enabled analysis jobs store the Go Redis job type
(e.g. finance_briefings). sfp-scheduler Resolve still accepts module_task.*
for one release so a mixed or rolled-back row keeps enqueueing.
"""

from __future__ import annotations

# Bare Redis job types accepted by sfp-scheduler jobs.Resolve / jobGroups.
GO_JOB_KEYS: frozenset[str] = frozenset(
    {
        'ai_analyze',
        'ai_batch',
        'auto_trade_scan',
        'board_warmup',
        'daily_list_open',
        'daily_list_scan',
        'daily_review',
        'eod_kline_sync',
        'factor_qc',
        'factor_scan',
        'feishu_push',
        'finance_briefings',
        'indicator_refresh',
        'klines_slow',
        'listings_sync',
        'market_heat_collect',
        'market_review',
        'market_sync',
        'mysql_to_influx',
        'position_monitor',
        'req_send',
        'req_summarize',
        'sentiment_analyze',
        'sentiment_collect',
        'stock_pick_run',
        'strategy_run',
        'symbol_content',
        'user_notice',
        'watchlist_analyze',
    }
)

GO_JOB_CATEGORY: dict[str, str] = {
    'ai_analyze': 'sentiment',
    'ai_batch': 'sentiment',
    'auto_trade_scan': 'trade',
    'board_warmup': 'market',
    'daily_list_open': 'trade',
    'daily_list_scan': 'quant',
    'daily_review': 'sentiment',
    'eod_kline_sync': 'market',
    'factor_qc': 'quant',
    'factor_scan': 'quant',
    'feishu_push': 'trade',
    'finance_briefings': 'market',
    'indicator_refresh': 'quant',
    'klines_slow': 'market',
    'listings_sync': 'market',
    'market_heat_collect': 'market',
    'market_review': 'market',
    'market_sync': 'market',
    'mysql_to_influx': 'market',
    'position_monitor': 'quant',
    'req_send': 'sentiment',
    'req_summarize': 'sentiment',
    'sentiment_analyze': 'sentiment',
    'sentiment_collect': 'sentiment',
    'stock_pick_run': 'market',
    'strategy_run': 'quant',
    'symbol_content': 'market',
    'user_notice': 'sentiment',
    'watchlist_analyze': 'market',
}

# Legacy Python invoke_target → (Go key, kwargs to set when the old row has none).
# kwargs is None when the Python path does not encode extra payload.
PYTHON_INVOKE_ALIASES: dict[str, tuple[str, str | None]] = {
    'module_task.sentiment_task.collect_and_analyze_job': ('sentiment_collect', None),
    'module_task.sentiment_task.collect_only_job': ('sentiment_collect', '{"analyze":false}'),
    'module_task.market_task.sync_market_job': ('market_sync', None),
    'module_task.market_task.sync_klines_slow_job': ('klines_slow', None),
    'module_task.market_task.sync_listings_job': ('listings_sync', None),
    'module_task.market_task.refresh_finance_briefings_job': ('finance_briefings', None),
    'module_task.market_task.refresh_symbol_content_job': ('symbol_content', None),
    'module_task.market_task.analyze_watchlist_job': ('watchlist_analyze', None),
    'module_task.market_task.analyze_market_review_job': ('market_review', None),
    'module_task.market_task.collect_market_heat_cn_job': ('market_heat_collect', '{"market":"CN"}'),
    'module_task.market_task.collect_market_heat_hk_job': ('market_heat_collect', '{"market":"HK"}'),
    'module_task.market_task.collect_market_heat_us_job': ('market_heat_collect', '{"market":"US"}'),
    'module_task.market_task.eod_kline_sync_cn_job': ('eod_kline_sync', '{"market":"CN"}'),
    'module_task.market_task.eod_kline_sync_hk_job': ('eod_kline_sync', '{"market":"HK"}'),
    'module_task.market_task.eod_kline_sync_us_job': ('eod_kline_sync', '{"market":"US"}'),
    'module_task.market_task.run_stock_pick_job': ('stock_pick_run', None),
    'module_task.quant_task.run_strategy_job': ('strategy_run', None),
    'module_task.quant_task.run_daily_factor_scan_job': ('factor_scan', None),
    'module_task.quant_task.run_position_monitor_job': ('position_monitor', None),
    'module_task.quant_task.run_indicator_refresh_job': ('indicator_refresh', None),
    'module_task.quant_task.run_factor_qc_job': ('factor_qc', None),
    'module_task.quant_task.run_daily_list_scan_job': ('daily_list_scan', None),
    'module_task.quant_task.run_daily_list_open_job': ('daily_list_open', None),
    'module_task.trade_task.run_auto_trade_scan_job': ('auto_trade_scan', None),
    'module_task.trade_task.run_feishu_push_job': ('feishu_push', None),
}

_TASK_CATEGORY = {
    'market_task': 'market',
    'quant_task': 'quant',
    'sentiment_task': 'sentiment',
    'trade_task': 'trade',
}


def is_go_invoke_target(target: str) -> bool:
    return str(target or '').strip() in GO_JOB_KEYS


def is_analysis_invoke_target(target: str) -> bool:
    text = str(target or '').strip()
    if is_go_invoke_target(text):
        return True
    if not text.startswith('module_task.') or 'scheduler_test' in text:
        return False
    return any(f'.{name}.' in text for name in _TASK_CATEGORY)


def category_from_invoke_target(target: str) -> str:
    text = str(target or '').strip()
    if text in GO_JOB_CATEGORY:
        return GO_JOB_CATEGORY[text]
    for module_name, category in _TASK_CATEGORY.items():
        if f'.{module_name}.' in text:
            return category
    return 'market'


def is_allowed_job_invoke_target(target: str) -> bool:
    """Admin job create/edit whitelist: Python module_task.* or a known Go key."""
    text = str(target or '').strip()
    if not text:
        return False
    if is_go_invoke_target(text):
        return True
    return text.startswith('module_task')
