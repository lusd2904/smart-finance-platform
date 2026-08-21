-- Alphalens 风格因子质检表 + 定时任务
-- 可重复执行。

CREATE TABLE IF NOT EXISTS quant_factor_qc (
  qc_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '质检ID',
  factor_key VARCHAR(32) NOT NULL COMMENT '因子键',
  factor_label VARCHAR(64) NULL COMMENT '因子中文名',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  horizon INT NOT NULL DEFAULT 1 COMMENT '前瞻收益天数',
  ic_mean DOUBLE NULL COMMENT '截面 IC 均值',
  ic_std DOUBLE NULL COMMENT '截面 IC 标准差',
  ir DOUBLE NULL COMMENT '信息比率 IC_mean/IC_std',
  spread DOUBLE NULL COMMENT '分位多空价差百分比',
  sample_dates INT NOT NULL DEFAULT 0 COMMENT '有效 IC 交易日数',
  symbol_count INT NOT NULL DEFAULT 0 COMMENT '截面标的数',
  as_of VARCHAR(16) NULL COMMENT 'K线截止日期',
  quantile_json TEXT NULL COMMENT '分位收益 JSON',
  payload_json TEXT NULL COMMENT '扩展载荷 JSON',
  create_time DATETIME NULL COMMENT '生成时间',
  PRIMARY KEY (qc_id),
  UNIQUE KEY uk_factor_qc (factor_key, market, horizon),
  KEY ix_qc_as_of (as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='量化因子质检（IC/IR/分位收益）';

DELETE FROM sys_job WHERE job_id = 108;
INSERT INTO sys_job VALUES
(108, '因子质检IC/IR', 'default', 'default', 'module_task.quant_task.run_factor_qc_job', NULL, NULL, '0 40 6 * * ?', '3', '1', '1', 'admin', sysdate(), '', NULL, '收盘后对美股股票池做 Alphalens 风格截面 IC/IR 与五分位收益质检');
