-- Pin Hang Seng + A-share benchmark indices in market_instrument so
-- eod_kline_sync / market_sync / board_warmup keep writing them.
-- Idempotent: INSERT IGNORE. Live hub already has the HK rows.
--
-- 上证指数 is 000001.SH only (Tencent sh000001).
-- Never INSERT/UPDATE bare 000001 here — live 000001 is 平安银行 (stock).

INSERT IGNORE INTO market_instrument (symbol, name, market, category, enabled, create_time)
VALUES
  ('HSI', '恒生指数', 'HK', 'index', '1', NOW()),
  ('HSTECH', '恒生科技指数', 'HK', 'index', '1', NOW()),
  ('HSCEI', '国企指数', 'HK', 'index', '1', NOW()),
  ('000001.SH', '上证指数', 'CN', 'index', '1', NOW()),
  ('399001', '深证成指', 'CN', 'index', '1', NOW()),
  ('399006', '创业板指', 'CN', 'index', '1', NOW());
