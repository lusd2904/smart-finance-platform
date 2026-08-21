-- 三市场收盘分析：表 + 菜单 + 定时任务
-- menu_id 2137-2139；job_id 110 / 111
-- 可重复执行。

CREATE TABLE IF NOT EXISTS market_daily_review (
  review_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '报告ID',
  market VARCHAR(10) NOT NULL COMMENT '市场 US/HK/CN',
  trade_date VARCHAR(10) NOT NULL COMMENT '交易日 YYYY-MM-DD',
  title VARCHAR(200) NULL COMMENT '标题',
  stance VARCHAR(16) NULL COMMENT '立场 偏多/偏空/中性',
  score INT NULL COMMENT '市场温度 0-100',
  summary TEXT NULL COMMENT '当日复盘摘要',
  index_review TEXT NULL COMMENT '指数与代表股解读',
  news_review TEXT NULL COMMENT '资讯解读',
  sentiment_review TEXT NULL COMMENT '舆情解读',
  outlook TEXT NULL COMMENT '次日关注',
  risk_warning TEXT NULL COMMENT '风险提示',
  source VARCHAR(16) NULL DEFAULT 'ai' COMMENT '来源 ai/rule',
  model_name VARCHAR(100) NULL COMMENT '模型名',
  context_json TEXT NULL COMMENT '分析上下文 JSON',
  raw_json TEXT NULL COMMENT '模型原始 JSON',
  analysis_time DATETIME NULL COMMENT '分析时间',
  PRIMARY KEY (review_id),
  UNIQUE KEY uk_market_daily_review (market, trade_date),
  KEY ix_review_date (trade_date),
  KEY ix_review_market_time (market, analysis_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='市场收盘分析日报';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2137 AND 2139;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2137 AND 2139;
DELETE FROM sys_job WHERE job_id IN (110, 111);

INSERT INTO sys_menu VALUES
('2137', '市场分析', '2100', '13', 'review', 'market/review/index', '', 'MarketReviewIndex', 1, 0, 'C', '0', '0', 'market:review:list', 'documentation', 'admin', sysdate(), '', null, '美股/港股/A股收盘复盘与历史'),
('2138', '复盘查询', '2137', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:review:list', '#', 'admin', sysdate(), '', null, ''),
('2139', '执行复盘', '2137', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:review:analyze', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES ('2', '2137'), ('2', '2138'), ('2', '2139');

INSERT INTO sys_job VALUES
(110, '亚太收盘市场分析', 'default', 'default', 'module_task.market_task.analyze_market_review_job', 'CN,HK', NULL, '0 35 16 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, 'A股/港股 16:00 收盘后生成当日复盘'),
(111, '美股收盘市场分析', 'default', 'default', 'module_task.market_task.analyze_market_review_job', 'US', NULL, '0 15 5 * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '美股 16:00 ET 收盘后（北京时间约 05:15）生成当日复盘');
