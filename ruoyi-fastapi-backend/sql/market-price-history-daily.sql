-- 日K历史行情表（存量迁移用，可重复执行）
-- 由 module_market/service/sync_service.py 迁出：服务层不再自动建表，
-- 表缺失时请执行 sql_migrate 或手动应用本文件。

CREATE TABLE IF NOT EXISTS market_price_history_daily (
  id BIGINT NOT NULL AUTO_INCREMENT,
  symbol VARCHAR(32) NOT NULL,
  market VARCHAR(10) NOT NULL DEFAULT 'US',
  trade_date VARCHAR(10) NOT NULL,
  open_price DOUBLE NULL,
  high_price DOUBLE NULL,
  low_price DOUBLE NULL,
  close_price DOUBLE NULL,
  volume DOUBLE NULL,
  turnover DOUBLE NULL,
  source VARCHAR(32) NULL DEFAULT 'sina',
  update_time DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_symbol_trade_date (symbol, trade_date),
  KEY ix_symbol (symbol),
  KEY ix_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日K历史行情表(存量迁移用)';
