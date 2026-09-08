-- APPLY AFTER DEPLOY
--
-- Run only after the sfp-scheduler release that adds Go-native invoke_target
-- aliases in jobs.Resolve is live. Until then, keep module_task.* paths so the
-- scheduler can still enqueue work (Python rollback remains valid either way).
--
-- Minimal cleanup (Ulisses): jobs 103, 107, 117.
UPDATE sys_job
SET invoke_target = 'finance_briefings'
WHERE job_id = 103
  AND invoke_target = 'module_task.market_task.refresh_finance_briefings_job';

UPDATE sys_job
SET invoke_target = 'indicator_refresh'
WHERE job_id = 107
  AND invoke_target = 'module_task.quant_task.run_indicator_refresh_job';

UPDATE sys_job
SET invoke_target = 'feishu_push'
WHERE job_id = 117
  AND invoke_target = 'module_task.trade_task.run_feishu_push_job';

-- Optional: remaining enabled production jobs (sfp-scheduler EnabledProductionIDs).
-- Uncomment after verifying scheduler + workers in your environment.
--
-- UPDATE sys_job SET invoke_target = 'market_sync'
-- WHERE job_id = 101 AND invoke_target = 'module_task.market_task.sync_market_job';
--
-- UPDATE sys_job SET invoke_target = 'symbol_content'
-- WHERE job_id = 104 AND invoke_target = 'module_task.market_task.refresh_symbol_content_job';
--
-- UPDATE sys_job SET invoke_target = 'market_heat_collect', job_kwargs = '{"market":"CN"}'
-- WHERE job_id = 113 AND invoke_target = 'module_task.market_task.collect_market_heat_cn_job';
--
-- UPDATE sys_job SET invoke_target = 'market_heat_collect', job_kwargs = '{"market":"HK"}'
-- WHERE job_id = 114 AND invoke_target = 'module_task.market_task.collect_market_heat_hk_job';
--
-- UPDATE sys_job SET invoke_target = 'market_heat_collect', job_kwargs = '{"market":"US"}'
-- WHERE job_id = 115 AND invoke_target = 'module_task.market_task.collect_market_heat_us_job';
--
-- UPDATE sys_job SET invoke_target = 'eod_kline_sync', job_kwargs = '{"market":"CN"}'
-- WHERE job_id = 121 AND invoke_target = 'module_task.market_task.eod_kline_sync_cn_job';
--
-- UPDATE sys_job SET invoke_target = 'eod_kline_sync', job_kwargs = '{"market":"HK"}'
-- WHERE job_id = 122 AND invoke_target = 'module_task.market_task.eod_kline_sync_hk_job';
--
-- UPDATE sys_job SET invoke_target = 'eod_kline_sync', job_kwargs = '{"market":"US"}'
-- WHERE job_id = 123 AND invoke_target = 'module_task.market_task.eod_kline_sync_us_job';
