-- 风控事件审批流字段（待复核/已确认/已忽略/需复核/超期）
-- 可重复执行：已存在的列会跳过。

CREATE TABLE IF NOT EXISTS plat_risk_event (
  event_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事件ID',
  rule_id BIGINT NULL COMMENT '关联规则ID',
  event_level VARCHAR(16) NOT NULL DEFAULT 'warn' COMMENT '事件等级',
  title VARCHAR(200) NOT NULL COMMENT '事件标题',
  content VARCHAR(1000) NULL COMMENT '事件详情',
  symbol VARCHAR(32) NULL COMMENT '标的代码',
  handled CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已处理（0否 1是）',
  review_status VARCHAR(32) NOT NULL DEFAULT 'pending_review' COMMENT '复核状态',
  handle_remark VARCHAR(500) NULL COMMENT '处理备注',
  handled_by VARCHAR(64) NULL COMMENT '处理人',
  handle_time DATETIME NULL COMMENT '处理时间',
  create_time DATETIME NULL COMMENT '触发时间',
  PRIMARY KEY (event_id),
  KEY ix_review_status (review_status),
  KEY ix_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控触发事件表';

SET @db := DATABASE();

SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_risk_event' AND COLUMN_NAME='review_status');
SET @sql := IF(@exists=0, 'ALTER TABLE plat_risk_event ADD COLUMN review_status VARCHAR(32) NOT NULL DEFAULT ''pending_review'' COMMENT ''复核状态'' AFTER handled', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_risk_event' AND COLUMN_NAME='handle_remark');
SET @sql := IF(@exists=0, 'ALTER TABLE plat_risk_event ADD COLUMN handle_remark VARCHAR(500) NULL COMMENT ''处理备注'' AFTER review_status', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_risk_event' AND COLUMN_NAME='handled_by');
SET @sql := IF(@exists=0, 'ALTER TABLE plat_risk_event ADD COLUMN handled_by VARCHAR(64) NULL COMMENT ''处理人'' AFTER handle_remark', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_risk_event' AND COLUMN_NAME='handle_time');
SET @sql := IF(@exists=0, 'ALTER TABLE plat_risk_event ADD COLUMN handle_time DATETIME NULL COMMENT ''处理时间'' AFTER handled_by', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE plat_risk_event
SET review_status = 'confirmed'
WHERE handled = '1' AND (review_status IS NULL OR review_status = '' OR review_status = 'pending_review');
