-- 市场热度看板 + Top50 快照：表 + 菜单 + 收盘采集任务 + 默认权重配置
-- menu_id 2600-2602（避开 ai-requirement-board 的 2140-2146）；job_id 113-115；config_id 500-502
-- 可重复执行。不删除 ai_req_item 与其它业务数据。

CREATE TABLE IF NOT EXISTS market_heat_daily (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  market VARCHAR(10) NOT NULL COMMENT '市场 US/HK/CN',
  trade_date VARCHAR(10) NOT NULL COMMENT '交易日 YYYY-MM-DD',
  index_symbol VARCHAR(32) NULL COMMENT '基准指数代码',
  index_name VARCHAR(100) NULL COMMENT '基准指数名称',
  index_change_pct DOUBLE NULL COMMENT '指数涨跌幅%',
  total_turnover DOUBLE NULL COMMENT '样本成交额合计',
  advance_count INT NULL COMMENT '上涨家数',
  decline_count INT NULL COMMENT '下跌家数',
  flat_count INT NULL COMMENT '平盘家数',
  heat_score DOUBLE NULL COMMENT '热度分 0-100',
  heat_summary VARCHAR(500) NULL COMMENT '热度摘要',
  currency VARCHAR(10) NULL COMMENT '成交额货币',
  filter_rule VARCHAR(200) NULL COMMENT 'Top50 市值过滤规则',
  weights_json TEXT NULL COMMENT '权重 JSON',
  as_of_time DATETIME NULL COMMENT '数据采集时间',
  status VARCHAR(20) NULL DEFAULT 'ok' COMMENT '状态 ok/stale/empty/error',
  message VARCHAR(500) NULL COMMENT '状态说明',
  create_time DATETIME NULL COMMENT '创建时间',
  update_time DATETIME NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_market_heat_daily (market, trade_date),
  KEY ix_market_heat_market_date (market, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分市场每日热度快照';

CREATE TABLE IF NOT EXISTS market_top50_snapshot (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  market VARCHAR(10) NOT NULL COMMENT '市场 US/HK/CN',
  trade_date VARCHAR(10) NOT NULL COMMENT '交易日 YYYY-MM-DD',
  rank_no INT NOT NULL COMMENT '排名 1-50',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  name VARCHAR(100) NULL COMMENT '名称',
  market_cap DOUBLE NULL COMMENT '市值',
  turnover DOUBLE NULL COMMENT '成交额',
  change_pct DOUBLE NULL COMMENT '涨跌幅%',
  currency VARCHAR(10) NULL COMMENT '货币',
  as_of_time DATETIME NULL COMMENT '快照时间',
  create_time DATETIME NULL COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_market_top50_symbol (market, trade_date, symbol),
  KEY ix_market_top50_market_date (market, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分市场 Top50 成交额快照';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2600 AND 2602;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2600 AND 2602;
DELETE FROM sys_job WHERE job_id BETWEEN 113 AND 115;

INSERT INTO sys_menu VALUES
('2600', '市场热度', '2100', '1', 'heat', 'market/heat/index', '', 'MarketHeatIndex', 1, 0, 'C', '0', '0', 'market:heat:list', 'data-analysis', 'admin', sysdate(), '', null, '三市场热度与 Top50 快照'),
('2601', '热度查询', '2600', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:heat:list', '#', 'admin', sysdate(), '', null, ''),
('2602', '热度采集', '2600', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:heat:collect', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES ('2', '2600'), ('2', '2601'), ('2', '2602');

INSERT INTO sys_job VALUES
(113, 'A股收盘热度采集', 'default', 'default', 'module_task.market_task.collect_market_heat_cn_job', NULL, NULL, '0 5 7 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, 'A股收盘后采集指数/成交额/A-D 与 Top50'),
(114, '港股收盘热度采集', 'default', 'default', 'module_task.market_task.collect_market_heat_hk_job', NULL, NULL, '0 5 8 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '港股收盘后采集指数/成交额/A-D 与 Top50'),
(115, '美股收盘热度采集', 'default', 'default', 'module_task.market_task.collect_market_heat_us_job', NULL, NULL, '0 5 21 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '美股收盘后采集指数/成交额/A-D 与 Top50');

INSERT INTO sys_config (config_id, config_name, config_key, config_value, config_type, create_by, create_time, update_by, update_time, remark)
SELECT 500, '热度权重-指数', 'market.heat.weight.index', '0.4', 'Y', 'admin', sysdate(), '', null, '市场热度指数涨跌权重'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'market.heat.weight.index');

INSERT INTO sys_config (config_id, config_name, config_key, config_value, config_type, create_by, create_time, update_by, update_time, remark)
SELECT 501, '热度权重-成交额', 'market.heat.weight.turnover', '0.3', 'Y', 'admin', sysdate(), '', null, '市场热度成交额权重'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'market.heat.weight.turnover');

INSERT INTO sys_config (config_id, config_name, config_key, config_value, config_type, create_by, create_time, update_by, update_time, remark)
SELECT 502, '热度权重-涨跌家数', 'market.heat.weight.advance_decline', '0.3', 'Y', 'admin', sysdate(), '', null, '市场热度涨跌家数权重'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'market.heat.weight.advance_decline');
