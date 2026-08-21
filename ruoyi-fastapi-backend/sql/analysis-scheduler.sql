-- 自动分析任务中心：独立调度微服务对应的菜单 + 补齐缺失任务
-- menu_id 2500-2505；job_id 103/104/112（已存在则跳过）
-- 可重复执行。

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2500 AND 2506;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2500 AND 2506;

INSERT INTO sys_menu VALUES
('2500', '任务中心', '0', '4', 'analysis', null, '', '', 1, 0, 'M', '0', '0', '', 'job', 'admin', sysdate(), '', null, '自动分析任务中心，调度在独立微服务中执行'),
('2501', '自动分析任务', '2500', '1', 'jobs', 'analysis/jobs/index', '', 'AnalysisJobsIndex', 1, 0, 'C', '0', '0', 'analysis:job:list', 'time-range', 'admin', sysdate(), '', null, '统一查看/启停/立即执行自动分析定时任务'),
('2502', '任务查询', '2501', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'analysis:job:list', '#', 'admin', sysdate(), '', null, ''),
('2503', '立即执行', '2501', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'analysis:job:run', '#', 'admin', sysdate(), '', null, ''),
('2504', '启停任务', '2501', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'analysis:job:edit', '#', 'admin', sysdate(), '', null, ''),
('2505', '任务日志', '2501', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'analysis:job:query', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2500'), ('2', '2501'), ('2', '2502'), ('2', '2503'), ('2', '2504'), ('2', '2505');

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 103, '财经资讯简报刷新', 'default', 'default', 'module_task.market_task.refresh_finance_briefings_job', NULL, NULL, '0 15 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '聚合内部简报与外部新闻写入 finance_briefing'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 103);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 104, '标的内容缓存刷新', 'default', 'default', 'module_task.market_task.refresh_symbol_content_job', NULL, NULL, '0 0/30 * * * ?', '3', '1', '1', 'admin', sysdate(), '', NULL, '长桥公告/资讯/讨论缓存，凭据配置后启用'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 104);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 112, '自动交易扫描', 'default', 'default', 'module_task.trade_task.run_auto_trade_scan_job', NULL, NULL, '0 0/15 * * * ?', '3', '1', '1', 'admin', sysdate(), '', NULL, '按策略扫描自选机会，默认只评估不向券商提交委托'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 112);
