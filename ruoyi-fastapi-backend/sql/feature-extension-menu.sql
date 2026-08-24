-- 补齐：股票池 / 智能推荐 / 风险概览 菜单
-- menu_id: 2130-2131 (market), 2230 (quant)
-- 注意：勿与 market-feature-extension.sql 的 2112/2113/2222 按钮冲突

DELETE FROM sys_role_menu WHERE menu_id IN (2130, 2131, 2230);
DELETE FROM sys_menu WHERE menu_id IN (2130, 2131, 2230);

INSERT INTO sys_menu VALUES
('2130', '标的股票池', '2100', '24', 'stock-pool', 'market/stock-pool/index', '', 'MarketStockPool', 1, 0, 'C', '1', '0', 'market:instrument:list', 'list', 'admin', sysdate(), '', null, '与行情台重叠，不单独占侧栏'),
('2131', '智能选股', '2100', '3', 'recommendations', 'market/recommendations/index', '', 'MarketRecommendations', 1, 0, 'C', '0', '0', 'market:picks:list', 'star', 'admin', sysdate(), '', null, '指标+舆情+开盘指数，休市去掉指数'),
('2230', '风险概览', '2200', '8', 'risk', 'quant/risk/index', '', 'QuantRiskOverview', 1, 0, 'C', '0', '0', 'quant:strategy:list', 'bug', 'admin', sysdate(), '', null, '风险概览');

INSERT INTO sys_role_menu VALUES ('2', '2130'), ('2', '2131'), ('2', '2230');
