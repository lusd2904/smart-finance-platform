-- Incremental: rewrite sys_job.invoke_target from module_task.* to Go keys.
-- Idempotent. Leaves module_task.scheduler_test.job (RuoYi demo) untouched.
-- Operator copy + before/after queries: scripts/migrate_sys_job_go_invoke_targets.sql

UPDATE sys_job SET invoke_target = 'sentiment_collect'
WHERE invoke_target = 'module_task.sentiment_task.collect_and_analyze_job';

UPDATE sys_job
SET invoke_target = 'sentiment_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"analyze":false}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.sentiment_task.collect_only_job';

UPDATE sys_job SET invoke_target = 'market_sync'
WHERE invoke_target = 'module_task.market_task.sync_market_job';

UPDATE sys_job SET invoke_target = 'klines_slow'
WHERE invoke_target = 'module_task.market_task.sync_klines_slow_job';

UPDATE sys_job SET invoke_target = 'listings_sync'
WHERE invoke_target = 'module_task.market_task.sync_listings_job';

UPDATE sys_job SET invoke_target = 'finance_briefings'
WHERE invoke_target = 'module_task.market_task.refresh_finance_briefings_job';

UPDATE sys_job SET invoke_target = 'symbol_content'
WHERE invoke_target = 'module_task.market_task.refresh_symbol_content_job';

UPDATE sys_job SET invoke_target = 'watchlist_analyze'
WHERE invoke_target = 'module_task.market_task.analyze_watchlist_job';

UPDATE sys_job SET invoke_target = 'market_review'
WHERE invoke_target = 'module_task.market_task.analyze_market_review_job';

UPDATE sys_job
SET invoke_target = 'market_heat_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"CN"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.collect_market_heat_cn_job';

UPDATE sys_job
SET invoke_target = 'market_heat_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"HK"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.collect_market_heat_hk_job';

UPDATE sys_job
SET invoke_target = 'market_heat_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"US"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.collect_market_heat_us_job';

UPDATE sys_job
SET invoke_target = 'eod_kline_sync',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"CN"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.eod_kline_sync_cn_job';

UPDATE sys_job
SET invoke_target = 'eod_kline_sync',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"HK"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.eod_kline_sync_hk_job';

UPDATE sys_job
SET invoke_target = 'eod_kline_sync',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"market":"US"}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.market_task.eod_kline_sync_us_job';

UPDATE sys_job SET invoke_target = 'stock_pick_run'
WHERE invoke_target = 'module_task.market_task.run_stock_pick_job';

UPDATE sys_job SET invoke_target = 'strategy_run'
WHERE invoke_target = 'module_task.quant_task.run_strategy_job';

UPDATE sys_job SET invoke_target = 'factor_scan'
WHERE invoke_target = 'module_task.quant_task.run_daily_factor_scan_job';

UPDATE sys_job SET invoke_target = 'position_monitor'
WHERE invoke_target = 'module_task.quant_task.run_position_monitor_job';

UPDATE sys_job SET invoke_target = 'indicator_refresh'
WHERE invoke_target = 'module_task.quant_task.run_indicator_refresh_job';

UPDATE sys_job SET invoke_target = 'factor_qc'
WHERE invoke_target = 'module_task.quant_task.run_factor_qc_job';

UPDATE sys_job SET invoke_target = 'daily_list_scan'
WHERE invoke_target = 'module_task.quant_task.run_daily_list_scan_job';

UPDATE sys_job SET invoke_target = 'daily_list_open'
WHERE invoke_target = 'module_task.quant_task.run_daily_list_open_job';

UPDATE sys_job SET invoke_target = 'auto_trade_scan'
WHERE invoke_target = 'module_task.trade_task.run_auto_trade_scan_job';

UPDATE sys_job SET invoke_target = 'feishu_push'
WHERE invoke_target = 'module_task.trade_task.run_feishu_push_job';
