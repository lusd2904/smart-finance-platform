-- 自动交易决策与扫描台账（create_all 兜底之外的显式建表）
CREATE TABLE IF NOT EXISTS plat_auto_trade_decision (
  decision_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '决策ID',
  cycle_id VARCHAR(64) NOT NULL COMMENT '扫描周期ID',
  account_id VARCHAR(64) NULL COMMENT '账户ID',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  side VARCHAR(10) NOT NULL COMMENT '买卖方向(BUY/SELL)',
  quantity INT NOT NULL COMMENT '委托数量',
  price DECIMAL(12,4) NULL COMMENT '下单参考价',
  confidence INT NULL COMMENT '置信度',
  status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '执行状态',
  reason TEXT NULL COMMENT '决策依据',
  source VARCHAR(32) NOT NULL DEFAULT 'auto' COMMENT '触发源',
  order_id VARCHAR(64) NULL COMMENT '券商真实委托单号',
  error TEXT NULL COMMENT '异常或拒绝原因',
  create_time DATETIME NULL COMMENT '创建时间',
  PRIMARY KEY (decision_id),
  KEY ix_cycle_id (cycle_id),
  KEY ix_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动交易决策与委托意图表';

CREATE TABLE IF NOT EXISTS plat_ai_trade_run_log (
  run_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '运行记录ID',
  cycle_id VARCHAR(64) NOT NULL COMMENT '周期唯一标识',
  source VARCHAR(32) NOT NULL DEFAULT 'scheduler' COMMENT '触发来源',
  strategy_profile VARCHAR(32) NOT NULL DEFAULT 'balanced' COMMENT '策略档位',
  target_count INT NOT NULL DEFAULT 0 COMMENT '扫描标的数',
  evaluated_count INT NOT NULL DEFAULT 0 COMMENT '已评估标的数',
  opportunity_count INT NOT NULL DEFAULT 0 COMMENT '发现机会数',
  submitted_orders_count INT NOT NULL DEFAULT 0 COMMENT '实际提交订单数',
  status VARCHAR(32) NOT NULL DEFAULT 'completed' COMMENT '运行状态',
  guardrail_snapshot TEXT NULL COMMENT '日内护栏快照JSON',
  candidates_snapshot TEXT NULL COMMENT '候选与评分快照JSON',
  opportunities_snapshot TEXT NULL COMMENT '机会标的快照JSON',
  skipped_reasons TEXT NULL COMMENT '跳过原因明细JSON',
  message TEXT NULL COMMENT '运行简述',
  started_at DATETIME NULL COMMENT '启动时间',
  finished_at DATETIME NULL COMMENT '结束时间',
  create_time DATETIME NULL COMMENT '记录时间',
  PRIMARY KEY (run_id),
  UNIQUE KEY uk_cycle_id (cycle_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自选股 AI 自动交易扫描台账';
