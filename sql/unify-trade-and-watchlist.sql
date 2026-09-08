-- 交易台入口合一：侧栏只留「行情交易」；量化自选迁入行情自选。
-- 可重复执行。

UPDATE sys_menu SET visible = '1', remark = '已并入 /trade/terminal'
WHERE menu_id IN (2401, 2429) AND visible <> '1';

UPDATE sys_menu SET path = 'terminal', component = 'market/terminal/index', route_name = 'TradeTerminalIndex'
WHERE menu_id = 2430;

INSERT INTO market_watchlist (user_id, symbol, market, name, note, enabled, sort_order, create_time, update_time)
SELECT q.user_id, q.symbol, q.market, NULL, q.note, IFNULL(q.enabled, '1'), 0, q.create_time, q.create_time
FROM quant_watchlist q
LEFT JOIN market_watchlist m
  ON m.user_id = q.user_id
 AND m.symbol COLLATE utf8mb4_general_ci = q.symbol COLLATE utf8mb4_general_ci
 AND m.market COLLATE utf8mb4_general_ci = q.market COLLATE utf8mb4_general_ci
WHERE m.id IS NULL;

UPDATE sys_config
SET config_value = 'https://github.com/lusd2904/smart-finance-platform/releases/latest'
WHERE config_key IN (
  'app.version.android.url',
  'app.version.macos.url',
  'app.version.windows.url'
) AND (config_value IS NULL OR config_value = '');
