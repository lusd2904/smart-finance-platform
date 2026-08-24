-- 全量业务菜单扩展：分市场/行情台/AI研判/交易中心/回测/通知/券商/台账
-- menu_id 段：
-- market 2120-2122（精确 ID，避免误删 deep-feature 的 2123/2124）
-- trade  2400-2429（避开 2300 系统设置中心，绝对不能使用 2300-2399）

-- 精确清理本文件 ID：不含 2408/2419/2420（deep-feature 风控）也不含 2300（系统设置中心）
DELETE FROM sys_role_menu WHERE menu_id IN (2120, 2121, 2122, 2421) OR menu_id BETWEEN 2400 AND 2407 OR menu_id BETWEEN 2410 AND 2418;
DELETE FROM sys_menu WHERE menu_id IN (2120, 2121, 2122, 2421) OR menu_id BETWEEN 2400 AND 2407 OR menu_id BETWEEN 2410 AND 2418;

-- 行情扩展
INSERT INTO sys_menu VALUES
('2120', '全部股票', '2100', '2', 'stocks', 'market/stocks/index', '', 'MarketStocksIndex', 1, 0, 'C', '0', '0', 'market:instrument:list', 'list', 'admin', sysdate(), '', null, '三市场全量代码分页列表'),
('2121', '行情台', '2100', '2', 'board', 'market/board/index', '', 'MarketBoardIndex', 1, 0, 'C', '0', '0', 'market:kline:list', 'chart', 'admin', sysdate(), '', null, '全市场报价入口，可点入 K 线/详情'),
('2122', 'AI研判', '2100', '5', 'ai-workbench', 'market/ai-workbench/index', '', 'MarketAiWorkbenchIndex', 1, 0, 'C', '0', '0', 'market:ai:analyze', 'skill', 'admin', sysdate(), '', null, '单标的与批量研判');

-- 交易中心目录（2400 段，绝不使用 2300-2399）
INSERT INTO sys_menu VALUES
('2400', '交易中心', '0', '5', 'trade', null, '', '', 1, 0, 'M', '0', '0', '', 'money', 'admin', sysdate(), '', null, '交易中心目录'),
('2401', '交易台', '2400', '1', 'trading', 'trade/trading/index', '', 'TradeTradingIndex', 1, 0, 'C', '0', '0', 'trade:order:submit', 'edit', 'admin', sysdate(), '', null, '交易台'),
('2402', '持仓', '2400', '2', 'positions', 'trade/positions/index', '', 'TradePositionsIndex', 1, 0, 'C', '0', '0', 'trade:position:list', 'list', 'admin', sysdate(), '', null, '持仓'),
('2403', '订单', '2400', '3', 'orders', 'trade/orders/index', '', 'TradeOrdersIndex', 1, 0, 'C', '0', '0', 'trade:order:list', 'form', 'admin', sysdate(), '', null, '订单'),
('2404', '策略回测', '2400', '4', 'backtest', 'trade/backtest/index', '', 'TradeBacktestIndex', 1, 0, 'C', '0', '0', 'trade:backtest:list', 'chart', 'admin', sysdate(), '', null, '策略回测'),
('2405', '通知中心', '2400', '5', 'notifications', 'trade/notifications/index', '', 'TradeNotificationsIndex', 1, 0, 'C', '0', '0', 'trade:notice:list', 'message', 'admin', sysdate(), '', null, '通知中心'),
('2406', 'AI交易台账', '2400', '6', 'ai-runs', 'trade/ai-runs/index', '', 'TradeAiRunsIndex', 1, 0, 'C', '0', '0', 'trade:aitrade:list', 'job', 'admin', sysdate(), '', null, 'AI交易台账'),
('2407', '券商账户', '2400', '7', 'broker', 'trade/broker/index', '', 'TradeBrokerIndex', 1, 0, 'C', '0', '0', 'trade:account:list', 'peoples', 'admin', sysdate(), '', null, '券商账户');

-- 按钮权限
INSERT INTO sys_menu VALUES
('2410', '账户查询', '2401', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:account:list', '#', 'admin', sysdate(), '', null, ''),
('2411', '持仓查询', '2402', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:position:list', '#', 'admin', sysdate(), '', null, ''),
('2412', '订单查询', '2403', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:order:list', '#', 'admin', sysdate(), '', null, ''),
('2413', '提交订单', '2401', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:order:submit', '#', 'admin', sysdate(), '', null, ''),
('2414', '撤单', '2403', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:order:cancel', '#', 'admin', sysdate(), '', null, ''),
('2415', '回测运行', '2404', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:backtest:run', '#', 'admin', sysdate(), '', null, ''),
('2416', '回测列表', '2404', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:backtest:list', '#', 'admin', sysdate(), '', null, ''),
('2417', '通知列表', '2405', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:notice:list', '#', 'admin', sysdate(), '', null, ''),
('2418', 'AI台账', '2406', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:aitrade:list', '#', 'admin', sysdate(), '', null, ''),
('2421', 'AI扫描执行', '2406', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:aitrade:run', '#', 'admin', sysdate(), '', null, '');

-- 普通角色授权（admin 超管仍可见全部）
-- 注意：仅授权本文件插入的 ID；2408/2409/2419/2420 由 deep-feature-menu.sql 负责
INSERT INTO sys_role_menu
SELECT '2', menu_id FROM sys_menu WHERE menu_id IN (2120, 2121, 2122, 2421) OR menu_id BETWEEN 2400 AND 2407 OR menu_id BETWEEN 2410 AND 2418;
