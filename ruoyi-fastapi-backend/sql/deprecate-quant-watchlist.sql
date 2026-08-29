-- 量化读写已走 market_watchlist；quant_watchlist 保留只读历史。
-- 不 DROP / 不 RENAME：module_quant ORM/DAO 仍引用该表。
-- 幂等：表存在则刷新 COMMENT，不存在则 no-op（仅登记 schema_version）。

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='quant_watchlist'
);
SET @sql := IF(
  @exists>0,
  'ALTER TABLE quant_watchlist COMMENT = ''DEPRECATED: live source is market_watchlist; retained as read-only history''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
