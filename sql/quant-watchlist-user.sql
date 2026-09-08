-- 量化自选池/策略运行/策略信号按登录用户隔离
-- 仅新增 user_id 列 + 索引，并把历史数据归到管理员(user_id=1)；不删除任何业务数据。
-- 可重复执行。

SET @db := DATABASE();

-- ------------------------------------------------------------- quant_watchlist ---
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_watchlist'
);

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_watchlist' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_watchlist ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''所属用户ID'' AFTER id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 历史空值归到管理员
SET @sql := IF(
    @table_exists>0,
    'UPDATE quant_watchlist SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 历史全局池去重：同 (user_id, symbol, market) 只保留最早一条，以便加唯一键
SET @sql := IF(
    @table_exists>0,
    'DELETE t1 FROM quant_watchlist t1 INNER JOIN quant_watchlist t2 ON t1.user_id = t2.user_id AND t1.symbol = t2.symbol AND t1.market = t2.market AND t1.id > t2.id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_watchlist'
      AND INDEX_NAME IN ('uk_quant_watchlist_user_symbol', 'uk_quant_watchlist_symbol_market')
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_watchlist ADD UNIQUE KEY uk_quant_watchlist_user_symbol (user_id, symbol, market)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_watchlist' AND INDEX_NAME='idx_quant_watchlist_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_watchlist ADD INDEX idx_quant_watchlist_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ----------------------------------------------------------- quant_strategy_run ---
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_run'
);

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_run' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_strategy_run ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''触发用户ID'' AFTER cycle_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @table_exists>0,
    'UPDATE quant_strategy_run SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_run' AND INDEX_NAME='idx_quant_strategy_run_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_strategy_run ADD INDEX idx_quant_strategy_run_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- --------------------------------------------------------- quant_strategy_signal ---
SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_signal'
);

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_signal' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_strategy_signal ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''归属用户ID'' AFTER run_id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := IF(
    @table_exists>0,
    'UPDATE quant_strategy_signal SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_strategy_signal' AND INDEX_NAME='idx_quant_strategy_signal_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_strategy_signal ADD INDEX idx_quant_strategy_signal_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
