-- 长桥凭据按登录用户隔离
-- 仅新增 user_id + 唯一键，并加宽 access_token；不插入任何 App Key / Secret / Token。
-- 可重复执行。

SET @db := DATABASE();

SET @table_exists := (
    SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config'
);

-- user_id
SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config' AND COLUMN_NAME='user_id'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_longbridge_config ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1 COMMENT ''用户ID'' AFTER id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 历史空值归到管理员
SET @sql := IF(
    @table_exists>0,
    'UPDATE quant_longbridge_config SET user_id = 1 WHERE user_id IS NULL OR user_id = 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- access_token 需容纳加密后的长 token（明文约 1116）
SET @sql := IF(
    @table_exists>0,
    'ALTER TABLE quant_longbridge_config MODIFY COLUMN access_token VARCHAR(2048) NULL COMMENT ''长桥Access Token''',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 旧单例若有重复行，只保留最早一条，以便加唯一键
SET @sql := IF(
    @table_exists>0,
    'DELETE t1 FROM quant_longbridge_config t1 INNER JOIN quant_longbridge_config t2 ON t1.user_id = t2.user_id AND t1.id > t2.id',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config' AND INDEX_NAME='uk_quant_longbridge_user'
);
SET @sql := IF(
    @table_exists>0 AND @exists=0,
    'ALTER TABLE quant_longbridge_config ADD UNIQUE KEY uk_quant_longbridge_user (user_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
