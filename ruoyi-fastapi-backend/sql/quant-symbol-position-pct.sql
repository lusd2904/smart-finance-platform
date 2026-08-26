-- 单标的仓位上限（占净资产比例），与日内买入额度分离。默认 10%，合法范围 5%–30%。
SET @db := DATABASE();

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_longbridge_config' AND COLUMN_NAME='max_symbol_position_pct'
);
SET @sql := IF(
    @exists=0,
    'ALTER TABLE quant_longbridge_config ADD COLUMN max_symbol_position_pct DOUBLE NOT NULL DEFAULT 0.10 COMMENT ''单标的持仓市值占净资产上限'' AFTER daily_buy_ratio',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
