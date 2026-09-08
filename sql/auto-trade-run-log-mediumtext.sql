-- 台账快照曾把每只标的的完整因子 JSON 写入 TEXT(64KB) 导致 1406。
-- 代码侧已改为只存摘要；列升 MEDIUMTEXT 作为兜底。
ALTER TABLE plat_ai_trade_run_log
  MODIFY COLUMN candidates_snapshot MEDIUMTEXT NULL COMMENT '候选与评分快照JSON',
  MODIFY COLUMN opportunities_snapshot MEDIUMTEXT NULL COMMENT '机会标的快照JSON',
  MODIFY COLUMN skipped_reasons MEDIUMTEXT NULL COMMENT '跳过原因明细JSON',
  MODIFY COLUMN guardrail_snapshot MEDIUMTEXT NULL COMMENT '日内护栏快照JSON';
