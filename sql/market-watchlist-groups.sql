-- 自选分组从 note 拆到独立列；旧数据把 note 拷到 groups，note 改回备注。
-- 可重复执行。

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_watchlist' AND COLUMN_NAME='groups'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_watchlist ADD COLUMN `groups` VARCHAR(255) NULL COMMENT ''分组，逗号分隔'' AFTER note',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE market_watchlist
SET `groups` = note
WHERE (`groups` IS NULL OR `groups` = '')
  AND note IS NOT NULL
  AND note <> '';
