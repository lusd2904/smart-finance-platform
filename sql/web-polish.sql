-- Web 完善：自选按用户隔离、策略权重 8 因子族对齐
-- 可重复执行。

SET @db := DATABASE();

-- market_watchlist.user_id
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist' AND COLUMN_NAME='user_id');
SET @sql := IF(@exists=0, 'ALTER TABLE market_watchlist ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER id', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist' AND INDEX_NAME='uk_market_watchlist_symbol');
SET @sql := IF(@exists>0, 'ALTER TABLE market_watchlist DROP INDEX uk_market_watchlist_symbol', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist' AND INDEX_NAME='uk_market_watchlist_user_symbol');
SET @sql := IF(@exists=0, 'ALTER TABLE market_watchlist ADD UNIQUE KEY uk_market_watchlist_user_symbol (user_id, symbol, market)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist' AND INDEX_NAME='ix_watchlist_user');
SET @sql := IF(@exists=0, 'ALTER TABLE market_watchlist ADD KEY ix_watchlist_user (user_id)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- market_watchlist_analysis.user_id
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist_analysis' AND COLUMN_NAME='user_id');
SET @sql := IF(@exists=0, 'ALTER TABLE market_watchlist_analysis ADD COLUMN user_id BIGINT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER watchlist_id', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist_analysis' AND INDEX_NAME='ix_watchlist_analysis_user');
SET @sql := IF(@exists=0, 'ALTER TABLE market_watchlist_analysis ADD KEY ix_watchlist_analysis_user (user_id, symbol, analysis_time)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE market_watchlist SET user_id = 1 WHERE user_id IS NULL OR user_id = 0;
UPDATE market_watchlist_analysis SET user_id = 1 WHERE user_id IS NULL OR user_id = 0;
