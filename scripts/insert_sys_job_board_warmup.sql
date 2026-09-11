-- Insert board_warmup into sys_job so sfp-scheduler cron-enqueues it.
-- Safe to re-run: skips when job_id 120 or invoke_target already exists.
--
-- Apply:
--   mysql ... < scripts/insert_sys_job_board_warmup.sql
--
-- After merge, rebuild sfp-market-worker and sentiment-data-api, then either
-- wait for this cron (every 10 min) or enqueue board_warmup once by hand.

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 120, '行情看板报价预热', 'default', 'default', 'board_warmup', NULL, NULL, '0 0/10 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '每10分钟从 Influx daily_kline 刷新 Redis sfp:cache:board:quotes'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 120)
  AND NOT EXISTS (SELECT 1 FROM sys_job WHERE invoke_target = 'board_warmup');
