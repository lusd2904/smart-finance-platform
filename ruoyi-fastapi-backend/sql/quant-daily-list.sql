-- 收盘后次日策略清单 + 长桥模拟开仓
-- menu_id 2235-2239；job_id 116/118。可重复执行。

CREATE TABLE IF NOT EXISTS quant_daily_list (
  list_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '清单ID',
  user_id BIGINT NOT NULL COMMENT '所属用户',
  scan_date DATE NOT NULL COMMENT '扫描日（收盘日）',
  trade_date DATE NOT NULL COMMENT '下一交易日',
  profile VARCHAR(20) NOT NULL DEFAULT 'balanced' COMMENT '策略档位',
  status VARCHAR(16) NOT NULL DEFAULT 'open' COMMENT 'open/empty/skipped',
  auto_enabled CHAR(1) NOT NULL DEFAULT '0' COMMENT '加入量化后持续自动交易',
  item_count INT NOT NULL DEFAULT 0,
  message VARCHAR(500) NULL,
  create_time DATETIME NULL,
  update_time DATETIME NULL,
  PRIMARY KEY (list_id),
  UNIQUE KEY uk_daily_list_user_trade (user_id, trade_date),
  KEY ix_daily_list_scan (scan_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='次日策略清单';

CREATE TABLE IF NOT EXISTS quant_daily_list_item (
  item_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '条目ID',
  list_id BIGINT NOT NULL COMMENT '清单ID',
  user_id BIGINT NOT NULL COMMENT '所属用户',
  trade_date DATE NOT NULL COMMENT '拟交易日',
  symbol VARCHAR(32) NOT NULL,
  market VARCHAR(10) NOT NULL DEFAULT 'US',
  name VARCHAR(64) NULL,
  `signal` VARCHAR(8) NOT NULL DEFAULT 'BUY',
  score DOUBLE NULL,
  confidence INT NULL,
  reason VARCHAR(500) NULL,
  selected CHAR(1) NOT NULL DEFAULT '0' COMMENT '用户勾选',
  auto_trade CHAR(1) NOT NULL DEFAULT '0' COMMENT '持续自动交易',
  status VARCHAR(16) NOT NULL DEFAULT 'listed' COMMENT 'listed/queued/submitted/filled/rejected/skipped',
  side VARCHAR(8) NOT NULL DEFAULT 'BUY',
  quantity INT NULL,
  price DOUBLE NULL,
  order_id VARCHAR(64) NULL,
  error VARCHAR(500) NULL,
  create_time DATETIME NULL,
  update_time DATETIME NULL,
  PRIMARY KEY (item_id),
  UNIQUE KEY uk_daily_item_user_symbol_day (user_id, symbol, market, trade_date, side),
  KEY ix_daily_item_list (list_id),
  KEY ix_daily_item_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='次日策略清单标的';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2235 AND 2239;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2235 AND 2239;

INSERT INTO sys_menu VALUES
('2235', '次日策略清单', '2200', '8', 'daily-list', 'quant/daily-list/index', '', 'QuantDailyListIndex', 1, 0, 'C', '0', '0', 'quant:dailylist:list', 'list', 'admin', sysdate(), '', null, '收盘扫描次日策略，勾选后长桥模拟开仓'),
('2236', '清单查询', '2235', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:dailylist:list', '#', 'admin', sysdate(), '', null, ''),
('2237', '扫描清单', '2235', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:dailylist:scan', '#', 'admin', sysdate(), '', null, ''),
('2238', '模拟开仓', '2235', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:dailylist:open', '#', 'admin', sysdate(), '', null, ''),
('2239', '加入量化', '2235', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:dailylist:auto', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2235'), ('2', '2236'), ('2', '2237'), ('2', '2238'), ('2', '2239');

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 116, '收盘后扫描次日策略清单', 'default', 'default', 'module_task.quant_task.run_daily_list_scan_job', NULL, NULL, '0 20 7 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, 'A股收盘后扫描策略，生成下一交易日清单；非交易日跳过'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 116);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 118, '开盘执行排队模拟单', 'default', 'default', 'module_task.quant_task.run_daily_list_open_job', NULL, NULL, '0 31 1 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, 'A股开盘后把排队的模拟开仓送到长桥模拟账户'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 118);
