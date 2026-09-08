-- Top50 快照补最新价 last。H5/Flutter 读 top50[].last；历史行保持 NULL，下次采集写入。
-- 可重复执行。不改写 market-heat.sql 基线。

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_top50_snapshot' AND COLUMN_NAME='last'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_top50_snapshot ADD COLUMN `last` DOUBLE NULL COMMENT ''最新价'' AFTER change_pct',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
