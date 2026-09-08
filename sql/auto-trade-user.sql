-- 自动交易决策/扫描台账按登录用户隔离
-- 仅新增 user_id 列 + 索引，历史数据归到管理员(user_id=1)；不删除任何业务数据。
-- 可重复执行。

SET @db := DATABASE();

-- ------------------------------------------------------ plat_auto_trade_decision ---
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_auto_trade_decision'
);

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_auto_trade_decision' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE plat_auto_trade_decision ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''所属用户ID'' AFTER cycle_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @table_exists>0,
    'UPDATE plat_auto_trade_decision SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_auto_trade_decision' AND INDEX_NAME='idx_auto_trade_decision_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE plat_auto_trade_decision ADD INDEX idx_auto_trade_decision_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- --------------------------------------------------------- plat_ai_trade_run_log ---
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_ai_trade_run_log'
);

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_ai_trade_run_log' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE plat_ai_trade_run_log ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''触发用户ID'' AFTER cycle_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @table_exists>0,
    'UPDATE plat_ai_trade_run_log SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='plat_ai_trade_run_log' AND INDEX_NAME='idx_ai_trade_run_log_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE plat_ai_trade_run_log ADD INDEX idx_ai_trade_run_log_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
