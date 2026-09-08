-- Migrate sys_job.invoke_target from Python module_task.* to Go-native job keys.
--
-- Safe to re-run: each UPDATE matches the old Python string only.
-- No downtime: sfp-scheduler Resolve still accepts both forms for one release.
-- Do not rewrite module_task.scheduler_test.job (RuoYi demo rows).
--
-- Apply (either path):
--   python3 scripts/sql_migrate.py apply
--     → sql/sys-job-go-invoke-targets.sql
--   mysql ... < scripts/migrate_sys_job_go_invoke_targets.sql
--
-- =====================================================================
-- BEFORE (run first; keep the result)
-- =====================================================================
-- SELECT COUNT(*) AS python_analysis
-- FROM sys_job
-- WHERE invoke_target LIKE 'module_task%'
--   AND invoke_target NOT LIKE 'module_task.scheduler_test%';
--
-- SELECT COUNT(*) AS go_native
-- FROM sys_job
-- WHERE invoke_target NOT LIKE 'module_task%';
--
-- SELECT job_id, job_name, status, invoke_target, job_args, job_kwargs
-- FROM sys_job
-- WHERE invoke_target LIKE 'module_task%'
--    OR invoke_target IN (
--         'sentiment_collect','market_sync','strategy_run','finance_briefings',
--         'symbol_content','factor_scan','position_monitor','indicator_refresh',
--         'factor_qc','watchlist_analyze','market_review','auto_trade_scan',
--         'market_heat_collect','daily_list_scan','feishu_push','daily_list_open',
--         'stock_pick_run','eod_kline_sync','klines_slow','listings_sync'
--       )
-- ORDER BY job_id;

-- --- sentiment ---
-- Job 100 舆情采集与AI分析: empty job_kwargs must be {"analyze":true}.
UPDATE sys_job
SET invoke_target = 'sentiment_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"analyze":true}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.sentiment_task.collect_and_analyze_job';

UPDATE sys_job
SET job_kwargs = '{"analyze":true}'
WHERE job_id = 100
  AND invoke_target = 'sentiment_collect'
  AND (job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}'));

UPDATE sys_job
SET invoke_target = 'sentiment_collect',
    job_kwargs = CASE
      WHEN job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}') THEN '{"analyze":false}'
      ELSE job_kwargs
    END
WHERE invoke_target = 'module_task.sentiment_task.collect_only_job';

-- --- market ---
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

-- --- quant ---
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

-- --- trade ---
UPDATE sys_job SET invoke_target = 'auto_trade_scan'
WHERE invoke_target = 'module_task.trade_task.run_auto_trade_scan_job';

UPDATE sys_job SET invoke_target = 'feishu_push'
WHERE invoke_target = 'module_task.trade_task.run_feishu_push_job';

-- =====================================================================
-- AFTER (expect python_analysis = 0; enabled rows use Go keys)
-- =====================================================================
-- SELECT COUNT(*) AS python_analysis
-- FROM sys_job
-- WHERE invoke_target LIKE 'module_task%'
--   AND invoke_target NOT LIKE 'module_task.scheduler_test%';
--
-- SELECT COUNT(*) AS leftover_unmapped
-- FROM sys_job
-- WHERE invoke_target LIKE 'module_task%'
--   AND invoke_target NOT LIKE 'module_task.scheduler_test%';
--
-- SELECT status, invoke_target, COUNT(*) AS n
-- FROM sys_job
-- WHERE invoke_target NOT LIKE 'module_task.scheduler_test%'
-- GROUP BY status, invoke_target
-- ORDER BY status, invoke_target;
--
-- -- Enabled production IDs (101,103,104,107,113-115,117,121-123) must be Go keys.
-- -- Job 100 (舆情采集与AI分析) job_kwargs must be {"analyze":true}:
-- SELECT job_id, invoke_target, job_kwargs, status
-- FROM sys_job
-- WHERE job_id IN (100,101,103,104,107,113,114,115,117,121,122,123)
-- ORDER BY job_id;
