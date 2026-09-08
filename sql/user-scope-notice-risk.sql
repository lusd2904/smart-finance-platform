-- 通知 / 风控事件 / 回测记录按登录账户隔离
-- 存量行回填 user_id=1（管理员），新写入必须带当前用户。

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_notification' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE plat_notification ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER notice_id, ADD KEY ix_notification_user_time (user_id, create_time)',
  'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_risk_event' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE plat_risk_event ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER event_id, ADD KEY ix_risk_event_user_time (user_id, create_time)',
  'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_backtest_run' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE plat_backtest_run ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER run_id, ADD KEY ix_backtest_user_time (user_id, create_time)',
  'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
