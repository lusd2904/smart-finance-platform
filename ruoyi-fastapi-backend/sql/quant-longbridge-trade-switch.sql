-- 交易开关按长桥账户（user_id）隔离。默认关闭；打开后该账户定时扫描/止损真实下单。
-- 同时恢复自动交易扫描与持仓止损两个调度任务（逐用户看开关，未打开的账户仍不下单）。
SET @db := DATABASE();

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config' AND COLUMN_NAME='auto_trade_enabled'
);
SET @sql := IF(
    @exists=0,
    'ALTER TABLE quant_longbridge_config ADD COLUMN auto_trade_enabled CHAR(1) NOT NULL DEFAULT ''0'' COMMENT ''本账户自动交易 0关1开（开则真实下单）'' AFTER region',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config' AND COLUMN_NAME='daily_buy_ratio'
);
SET @sql := IF(
    @exists=0,
    'ALTER TABLE quant_longbridge_config ADD COLUMN daily_buy_ratio DOUBLE NOT NULL DEFAULT 0.20 COMMENT ''日内买入占净资产比例'' AFTER auto_trade_enabled',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE sys_job SET status = '0' WHERE job_id IN (106, 112) AND status = '1';
