-- 行情中心自选清单：表 + 菜单 + 每小时 AI 综合分析任务
-- menu_id 2132-2136；job_id 109
-- 可重复执行。

CREATE TABLE IF NOT EXISTS market_watchlist (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id BIGINT NOT NULL DEFAULT 1 COMMENT '用户ID',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场 US/HK/CN',
  name VARCHAR(100) NULL COMMENT '名称',
  note VARCHAR(255) NULL COMMENT '备注',
  enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否启用（0否 1是）',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  create_time DATETIME NULL COMMENT '加入时间',
  update_time DATETIME NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_market_watchlist_user_symbol (user_id, symbol, market),
  KEY ix_watchlist_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行情中心自选清单';

CREATE TABLE IF NOT EXISTS market_watchlist_analysis (
  analysis_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '分析ID',
  watchlist_id BIGINT NULL COMMENT '自选ID',
  user_id BIGINT NULL DEFAULT 1 COMMENT '用户ID',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  price DOUBLE NULL COMMENT '分析时价格',
  change_percent DOUBLE NULL COMMENT '涨跌幅百分比',
  stance VARCHAR(16) NULL COMMENT '立场 偏多/偏空/中性',
  recommendation VARCHAR(16) NULL COMMENT '建议',
  confidence INT NULL COMMENT '置信度 0-100',
  summary TEXT NULL COMMENT '综合摘要',
  indicator_review TEXT NULL COMMENT '指标解读',
  news_review TEXT NULL COMMENT '长桥资讯解读',
  sentiment_review TEXT NULL COMMENT '舆情解读',
  operation_advice TEXT NULL COMMENT '操作建议',
  risk_warning TEXT NULL COMMENT '风险提示',
  source VARCHAR(16) NULL DEFAULT 'ai' COMMENT '来源 ai/rule',
  model_name VARCHAR(100) NULL COMMENT '模型名',
  indicators_json TEXT NULL COMMENT '指标快照 JSON',
  news_json TEXT NULL COMMENT '资讯摘要 JSON',
  sentiment_json TEXT NULL COMMENT '舆情摘要 JSON',
  raw_json TEXT NULL COMMENT '模型原始 JSON',
  analysis_time DATETIME NULL COMMENT '分析时间',
  PRIMARY KEY (analysis_id),
  KEY ix_watchlist_symbol_time (symbol, analysis_time),
  KEY ix_watchlist_id (watchlist_id),
  KEY ix_watchlist_analysis_user (user_id, symbol, analysis_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行情自选综合分析';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2132 AND 2136;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2132 AND 2136;
DELETE FROM sys_job WHERE job_id = 109;

INSERT INTO sys_menu VALUES
('2132', '自选清单', '2100', '12', 'watchlist', 'market/watchlist/index', '', 'MarketWatchlistIndex', 1, 0, 'C', '0', '0', 'market:watchlist:list', 'star', 'admin', sysdate(), '', null, '行情中心自选清单，小时级 AI 综合分析'),
('2133', '自选查询', '2132', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:watchlist:list', '#', 'admin', sysdate(), '', null, ''),
('2134', '自选新增', '2132', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:watchlist:add', '#', 'admin', sysdate(), '', null, ''),
('2135', '自选删除', '2132', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:watchlist:remove', '#', 'admin', sysdate(), '', null, ''),
('2136', '自选分析', '2132', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:watchlist:analyze', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES ('2', '2132'), ('2', '2133'), ('2', '2134'), ('2', '2135'), ('2', '2136');

INSERT INTO sys_job VALUES
(109, '自选清单小时分析', 'default', 'default', 'module_task.market_task.analyze_watchlist_job', NULL, NULL, '0 20 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '每小时综合技术指标、长桥资讯与舆情对行情自选给出建议');
