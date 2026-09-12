-- Pin Hang Seng + A-share benchmark indices in market_instrument so
-- eod_kline_sync / market_sync / board_warmup keep writing them.
-- Idempotent: INSERT IGNORE. Live hub already has the HK rows.
--
-- CN 000001 is 上证指数 (Tencent sh000001), NOT 000001.SZ 平安银行.

INSERT IGNORE INTO market_instrument (symbol, name, market, category, enabled, create_time)
VALUES
  ('HSI', '恒生指数', 'HK', 'index', '1', NOW()),
  ('HSTECH', '恒生科技指数', 'HK', 'index', '1', NOW()),
  ('HSCEI', '国企指数', 'HK', 'index', '1', NOW()),
  ('000001', '上证指数', 'CN', 'index', '1', NOW()),
  ('399001', '深证成指', 'CN', 'index', '1', NOW()),
  ('399006', '创业板指', 'CN', 'index', '1', NOW());
