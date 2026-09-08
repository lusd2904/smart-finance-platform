-- Job 100 (舆情采集与AI分析) often has empty job_kwargs on live cron.
-- sentiment_collect must enqueue {"analyze":true}; notify-worker also
-- defaults omitted analyze to true and then honors sentiment_ai_config.auto_analyze.
-- Idempotent. Does not rewrite collect-only rows that already set analyze:false.

UPDATE sys_job
SET job_kwargs = '{"analyze":true}'
WHERE job_id = 100
  AND invoke_target IN ('sentiment_collect', 'module_task.sentiment_task.collect_and_analyze_job')
  AND (job_kwargs IS NULL OR TRIM(job_kwargs) IN ('', '{}'));
