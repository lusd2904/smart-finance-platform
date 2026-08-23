-- 全市场智能选股 + 三市场收盘拉日K/分时（可重复执行）
-- menu 复用 2131；按钮 2610-2611；job 119 / 121-123

CREATE TABLE IF NOT EXISTS market_stock_pick (
  pick_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '选股单ID',
  trade_date VARCHAR(10) NOT NULL COMMENT '交易日',
  status VARCHAR(16) NOT NULL DEFAULT 'ok' COMMENT 'running/ok/partial/empty/error',
  trigger_source VARCHAR(16) NULL DEFAULT 'manual',
  scanned_count INT NULL DEFAULT 0,
  picked_count INT NULL DEFAULT 0,
  ai_count INT NULL DEFAULT 0,
  model_name VARCHAR(100) NULL,
  open_markets VARCHAR(32) NULL,
  context_json TEXT NULL,
  message VARCHAR(500) NULL,
  create_time DATETIME NULL,
  update_time DATETIME NULL,
  PRIMARY KEY (pick_id),
  UNIQUE KEY uk_market_stock_pick_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全市场智能选股单';

CREATE TABLE IF NOT EXISTS market_stock_pick_item (
  item_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '条目ID',
  pick_id BIGINT NOT NULL,
  rank_no INT NOT NULL DEFAULT 0,
  symbol VARCHAR(32) NOT NULL,
  name VARCHAR(100) NULL,
  market VARCHAR(10) NOT NULL DEFAULT 'US',
  price DOUBLE NULL,
  change_pct DOUBLE NULL,
  factor_score DOUBLE NULL,
  pick_score DOUBLE NULL,
  `signal` VARCHAR(8) NULL,
  recommendation VARCHAR(16) NULL,
  stance VARCHAR(16) NULL,
  confidence INT NULL,
  summary TEXT NULL,
  indicator_review TEXT NULL,
  sentiment_review TEXT NULL,
  operation_advice TEXT NULL,
  risk_warning TEXT NULL,
  tags_json TEXT NULL,
  source VARCHAR(16) NULL DEFAULT 'rule',
  factor_json TEXT NULL,
  create_time DATETIME NULL,
  PRIMARY KEY (item_id),
  UNIQUE KEY uk_market_stock_pick_item (pick_id, symbol, market),
  KEY ix_pick_item_pick (pick_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全市场智能选股条目';

-- 侧栏：智能选股
UPDATE sys_menu
SET visible = '0',
    menu_name = '智能选股',
    order_num = 3,
    icon = 'star',
    perms = 'market:picks:list',
    remark = '指标+舆情+开盘指数，休市去掉指数'
WHERE parent_id = 2100 AND path = 'recommendations' AND menu_type = 'C';

UPDATE sys_menu SET order_num = 4 WHERE parent_id = 2100 AND path = 'board' AND menu_type = 'C';
UPDATE sys_menu SET order_num = 5 WHERE parent_id = 2100 AND path = 'watchlist' AND menu_type = 'C';
UPDATE sys_menu SET order_num = 6 WHERE parent_id = 2100 AND path = 'finance-news' AND menu_type = 'C';
UPDATE sys_menu SET order_num = 7 WHERE parent_id = 2100 AND path = 'ai-workbench' AND menu_type = 'C';

DELETE FROM sys_role_menu WHERE menu_id IN (2610, 2611);
DELETE FROM sys_menu WHERE menu_id IN (2610, 2611);
INSERT INTO sys_menu VALUES
('2610', '选股查询', '2131', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:picks:list', '#', 'admin', sysdate(), '', null, ''),
('2611', '生成选股单', '2131', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:picks:run', '#', 'admin', sysdate(), '', null, '');
INSERT IGNORE INTO sys_role_menu VALUES ('2', '2131'), ('2', '2610'), ('2', '2611');

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 119, '全市场智能选股', 'default', 'default', 'module_task.market_task.run_stock_pick_job', NULL, NULL, '0 50 7,8,21 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '三市场收盘后选股（UTC 07:50/08:50/21:50=北京 15:50/16:50/05:50）；可在任务中心改 cron'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 119);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 121, 'A股收盘拉日K与分时', 'default', 'default', 'module_task.market_task.eod_kline_sync_cn_job', NULL, NULL, '0 25 7 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, 'A股收盘后增量日K+分时（UTC 07:25=北京 15:25）'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 121);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 122, '港股收盘拉日K与分时', 'default', 'default', 'module_task.market_task.eod_kline_sync_hk_job', NULL, NULL, '0 25 8 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '港股收盘后增量日K+分时（UTC 08:25=北京 16:25）'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 122);

INSERT INTO sys_job (job_id, job_name, job_group, job_executor, invoke_target, job_args, job_kwargs, cron_expression, misfire_policy, concurrent, status, create_by, create_time, update_by, update_time, remark)
SELECT 123, '美股收盘拉日K与分时', 'default', 'default', 'module_task.market_task.eod_kline_sync_us_job', NULL, NULL, '0 25 21 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '美股收盘后增量日K+分时（UTC 21:25=北京 05:25）'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM sys_job WHERE job_id = 123);

-- 智能选股默认 Grok 4.6（适用范围 market）。已有行情模型不覆盖；凭据复用当前启用模型。
-- OpenRouter 模型编码为 x-ai/grok-4.6，直连 xAI 为 grok-4.6。换模型：AI 管理 → 模型管理。
INSERT INTO ai_models (
  model_code, model_name, provider, model_sort, scope, api_key, base_url,
  model_type, max_tokens, temperature, support_reasoning, support_images,
  status, create_by, create_time, remark
)
SELECT
  CASE WHEN LOWER(IFNULL(src.base_url, '')) LIKE '%openrouter%' THEN 'x-ai/grok-4.6' ELSE 'grok-4.6' END,
  'Grok 4.6',
  CASE WHEN LOWER(IFNULL(src.base_url, '')) LIKE '%openrouter%' THEN 'OpenRouter' ELSE 'xAI' END,
  0,
  'market',
  src.api_key,
  src.base_url,
  src.model_type,
  src.max_tokens,
  IFNULL(src.temperature, 0.2),
  'Y',
  'N',
  '0',
  'admin',
  sysdate(),
  '智能选股默认模型；适用范围=行情中心(market)，可在 AI 模型管理更换'
FROM (
  SELECT * FROM ai_models
  WHERE status = '0'
    AND IFNULL(base_url, '') <> ''
    AND IFNULL(api_key, '') <> ''
  ORDER BY model_sort, model_id
  LIMIT 1
) src
WHERE NOT EXISTS (SELECT 1 FROM ai_models m2 WHERE m2.scope = 'market');
