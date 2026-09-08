-- Top50 快照补涨跌额 / 换手率 / 量比 / 振幅 / PE / 主力净流入。
-- 历史行保持 NULL，下次采集写入。可重复执行。不改写 market-heat.sql 基线。
-- 新列挂在 change_pct 后：文件名排在 market-top50-last.sql 之前，不能依赖 last 已存在。

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='change_amount'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `change_amount` DOUBLE NULL COMMENT ''涨跌额'' AFTER change_pct',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='turnover_rate'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `turnover_rate` DOUBLE NULL COMMENT ''换手率%'' AFTER change_amount',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='volume_ratio'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `volume_ratio` DOUBLE NULL COMMENT ''量比'' AFTER turnover_rate',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='amplitude'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `amplitude` DOUBLE NULL COMMENT ''振幅%'' AFTER volume_ratio',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='pe'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `pe` DOUBLE NULL COMMENT ''市盈率'' AFTER amplitude',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='main_net_inflow'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `main_net_inflow` DOUBLE NULL COMMENT ''主力净流入'' AFTER pe',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
