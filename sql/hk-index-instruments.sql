-- Hang Seng family: durable market_instrument rows so eod_kline_sync /
-- board_warmup keep writing and showing HSI / HSTECH / HSCEI even after
-- a fresh compose seed. Idempotent. Live hub may already have the rows.
--
--   python3 scripts/sql_migrate.py apply --file hk-index-instruments.sql
--
-- Do not recreate mysql. INSERT IGNORE is enough when the unique key is
-- symbol; ON DUPLICATE also re-enables and forces category=index.

INSERT INTO market_instrument (symbol, name, market, category, enabled, create_time)
VALUES
  ('HSI', '恒生指数', 'HK', 'index', '1', NOW()),
  ('HSTECH', '恒生科技指数', 'HK', 'index', '1', NOW()),
  ('HSCEI', '恒生中国企业指数', 'HK', 'index', '1', NOW())
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  market = 'HK',
  category = 'index',
  enabled = '1';
