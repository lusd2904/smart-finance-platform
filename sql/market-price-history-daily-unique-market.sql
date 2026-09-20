-- 日K唯一键补上 market，避免同代码不同市场互相覆盖。
-- 可重复执行。不改写 market-price-history-daily.sql 基线。

-- 同一 (symbol, market, trade_date) 只留 id 最大的一行。
DELETE d FROM market_price_history_daily d
INNER JOIN (
  SELECT symbol, market, trade_date, MAX(id) AS keep_id
  FROM market_price_history_daily
  GROUP BY symbol, market, trade_date
  HAVING COUNT(*) > 1
) dup
  ON d.symbol = dup.symbol
 AND d.market = dup.market
 AND d.trade_date = dup.trade_date
 AND d.id <> dup.keep_id;

SET @db := DATABASE();

SET @exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_price_history_daily' AND INDEX_NAME='uniq_symbol_trade_date'
);
SET @sql := IF(
  @exists>0,
  'ALTER TABLE market_price_history_daily DROP INDEX uniq_symbol_trade_date',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='market_price_history_daily' AND INDEX_NAME='uniq_symbol_market_trade_date'
);
SET @sql := IF(
  @exists=0,
  'ALTER TABLE market_price_history_daily ADD UNIQUE KEY uniq_symbol_market_trade_date (symbol, market, trade_date)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
