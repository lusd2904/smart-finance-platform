-- Phase 2：高阶因子快照表 + 读模型快照 + 定时任务
-- 可重复执行。

CREATE TABLE IF NOT EXISTS quant_factor_snapshot (
  snapshot_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '快照ID',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  as_of VARCHAR(16) NULL COMMENT 'K线截止日期',
  score_total DOUBLE NULL COMMENT '综合打分',
  risk_level VARCHAR(16) NULL COMMENT '风险等级',
  trend_direction VARCHAR(16) NULL COMMENT '趋势方向',
  alpha101_count INT NOT NULL DEFAULT 0 COMMENT 'Alpha101 个数',
  alpha158_count INT NOT NULL DEFAULT 0 COMMENT 'Alpha158 个数',
  score_json TEXT NULL COMMENT '8 大因子族得分 JSON',
  alpha_json TEXT NULL COMMENT '高阶因子 JSON',
  create_time DATETIME NULL COMMENT '生成时间',
  PRIMARY KEY (snapshot_id),
  UNIQUE KEY uk_symbol_market (symbol, market),
  KEY ix_score_total (score_total)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='量化因子定时快照';

CREATE TABLE IF NOT EXISTS quant_readmodel_snapshot (
  snapshot_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '快照ID',
  snapshot_type VARCHAR(32) NOT NULL COMMENT '快照类型',
  payload_json TEXT NOT NULL COMMENT '快照 JSON',
  create_time DATETIME NULL COMMENT '生成时间',
  PRIMARY KEY (snapshot_id),
  KEY ix_type_time (snapshot_type, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='读模型聚合快照';

DELETE FROM sys_job WHERE job_id IN (105, 106, 107);
INSERT INTO sys_job VALUES
(105, '全市场因子日扫', 'default', 'default', 'module_task.quant_task.run_daily_factor_scan_job', NULL, NULL, '0 10 6 * * ?', '3', '1', '1', 'admin', sysdate(), '', NULL, '每日收盘后计算 Alpha101/158 与 8 大因子族并写入读模型快照'),
(106, '持仓止损监控', 'default', 'default', 'module_task.quant_task.run_position_monitor_job', NULL, NULL, '0 0/10 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '每 10 分钟检查持仓浮亏，超阈值写入风控事件'),
(107, '行情指标快照刷新', 'default', 'default', 'module_task.quant_task.run_indicator_refresh_job', NULL, NULL, '0 0/15 * * * ?', '3', '1', '0', 'admin', sysdate(), '', NULL, '每 15 分钟刷新目标池最新价与涨跌快照');
