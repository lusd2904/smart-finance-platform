-- 飞书策略摘要推送：个人会话 + 群 Webhook，用户自设时间
-- menu_id 2425-2428；job_id 117。可重复执行。

CREATE TABLE IF NOT EXISTS plat_feishu_subscription (
  sub_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '订阅ID',
  user_id BIGINT NOT NULL COMMENT '用户ID',
  personal_enabled CHAR(1) NOT NULL DEFAULT '0' COMMENT '个人会话',
  group_enabled CHAR(1) NOT NULL DEFAULT '0' COMMENT '群',
  personal_webhook VARCHAR(500) NULL COMMENT '个人机器人 Webhook',
  group_webhook VARCHAR(500) NULL COMMENT '群机器人 Webhook',
  push_time VARCHAR(8) NOT NULL DEFAULT '18:30' COMMENT '用户本地推送时刻 HH:MM',
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
  last_personal_key VARCHAR(64) NULL COMMENT '去重键 user:personal:tradeDate',
  last_group_key VARCHAR(64) NULL,
  last_error VARCHAR(500) NULL,
  update_time DATETIME NULL,
  create_time DATETIME NULL,
  PRIMARY KEY (sub_id),
  UNIQUE KEY uk_feishu_sub_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='飞书策略摘要订阅';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2425 AND 2428;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2425 AND 2428;

INSERT INTO sys_menu VALUES
('2425', '飞书推送', '2400', '9', 'feishu-push', 'trade/feishu-push/index', '', 'TradeFeishuPushIndex', 1, 0, 'C', '0', '0', 'trade:feishu:query', 'message', 'admin', sysdate(), '', null, '订阅飞书个人/群策略摘要，自设推送时间'),
('2426', '订阅查询', '2425', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:feishu:query', '#', 'admin', sysdate(), '', null, ''),
('2427', '订阅保存', '2425', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:feishu:edit', '#', 'admin', sysdate(), '', null, ''),
('2428', '测试推送', '2425', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:feishu:test', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2425'), ('2', '2426'), ('2', '2427'), ('2', '2428');

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 117, '飞书策略摘要推送', 'default', 'default', 'module_task.trade_task.run_feishu_push_job', NULL, NULL, '0 0/5 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '按用户时区与交易日历推送次日策略摘要；非交易日/空清单静默'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 117);
