-- 加深能力菜单：风控管理、行情覆盖、高级图表、策略配置
-- 风控管理挂在交易中心(2400)下，使用 2408/2419/2420（避开 2300 系统设置中心）
-- 行情覆盖/高级图表 2123-2124；策略配置 2225

DELETE FROM sys_role_menu WHERE menu_id IN (2123, 2124, 2225, 2408, 2419, 2420);
DELETE FROM sys_menu WHERE menu_id IN (2123, 2124, 2225, 2408, 2419, 2420);

INSERT INTO sys_menu VALUES
('2123', '行情覆盖', '2100', '27', 'coverage', 'market/coverage/index', '', 'MarketCoverage', 1, 0, 'C', '1', '0', 'market:kline:list', 'redis', 'admin', sysdate(), '', null, '覆盖检测，不单独占侧栏'),
('2124', '高级图表', '2100', '28', 'tradingview', 'market/tradingview/index', '', 'MarketTradingview', 1, 0, 'C', '1', '0', 'market:kline:list', 'chart', 'admin', sysdate(), '', null, '从 K 线/覆盖点入，不单独占侧栏'),
('2225', '策略配置', '2200', '9', 'strategy-config', 'quant/strategy-config/index', '', 'QuantStrategyConfig', 1, 0, 'C', '0', '0', 'quant:strategy:list', 'edit', 'admin', sysdate(), '', null, '策略配置'),
('2408', '风控管理', '2400', '8', 'risk', 'trade/risk/index', '', 'TradeRiskIndex', 1, 0, 'C', '0', '0', 'trade:risk:list', 'bug', 'admin', sysdate(), '', null, '风控管理'),
('2419', '风控查询', '2408', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:risk:list', '#', 'admin', sysdate(), '', null, ''),
('2420', '风控编辑', '2408', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:risk:edit', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2','2123'),('2','2124'),('2','2225'),('2','2408'),('2','2419'),('2','2420');
