-- 分钟K历史行情表（phase 1 双写仍在，读者已切 MySQL；可重复执行）
-- market-worker 在写入 Influx minute_kline 后镜像到本表。
-- 读路径已切到 MySQL（market-read / trade-api / notify-worker / quant-worker / opensync）。
-- Influx 写入仍保留，拆除 Influx 是后续运维步骤；本文件不改 compose / mem_limits。
-- 表缺失时请执行 sql_migrate 或手动应用本文件。
-- 未分区：现有 MySQL 8.0 上 RANGE 分区迁移成本高；靠唯一键与索引支撑
-- (symbol, market, 时间范围) 查询与 (market, time) last-print，后续用 trade_date 裁剪约 20 个交易日。

CREATE TABLE IF NOT EXISTS market_price_history_minute (
  id BIGINT NOT NULL AUTO_INCREMENT,
  symbol VARCHAR(32) NOT NULL,
  market VARCHAR(10) NOT NULL DEFAULT 'US',
  trade_date VARCHAR(10) NOT NULL,
  bar_time DATETIME NOT NULL,
  open_price DOUBLE NULL,
  high_price DOUBLE NULL,
  low_price DOUBLE NULL,
  close_price DOUBLE NULL,
  volume DOUBLE NULL,
  source VARCHAR(32) NULL DEFAULT 'tencent',
  update_time DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_symbol_market_bar_time (symbol, market, bar_time),
  KEY ix_market_bar_time (market, bar_time),
  KEY ix_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分钟K历史(读者MySQL,Influx仍双写)';
