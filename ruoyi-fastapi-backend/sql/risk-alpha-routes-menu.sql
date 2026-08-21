-- 风险复核 / Alpha 快照 前端路由菜单
-- /trade/risk-review  ·  /quant/alpha-snapshot
-- menu_id: 2422-2424 (trade), 2231-2233 (quant)

DELETE FROM sys_role_menu WHERE menu_id IN (2422, 2423, 2424, 2231, 2232, 2233);
DELETE FROM sys_menu WHERE menu_id IN (2422, 2423, 2424, 2231, 2232, 2233);

INSERT INTO sys_menu VALUES
('2422', '风险复核', '2400', '9', 'risk-review', 'trade/risk-review/index', '', 'TradeRiskReview', 1, 0, 'C', '0', '0', 'trade:risk:list', 'edit', 'admin', sysdate(), '', null, '风险事件复核审批'),
('2423', '复核查询', '2422', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:risk:list', '#', 'admin', sysdate(), '', null, ''),
('2424', '复核处理', '2422', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'trade:risk:edit', '#', 'admin', sysdate(), '', null, ''),
('2231', 'Alpha快照', '2200', '7', 'alpha-snapshot', 'quant/alpha-snapshot/index', '', 'QuantAlphaSnapshot', 1, 0, 'C', '0', '0', 'quant:factor:list', 'chart', 'admin', sysdate(), '', null, 'Alpha101/158 读模型快照'),
('2232', '快照查询', '2231', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:factor:list', '#', 'admin', sysdate(), '', null, ''),
('2233', '日扫执行', '2231', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:strategy:run', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2422'), ('2', '2423'), ('2', '2424'),
('2', '2231'), ('2', '2232'), ('2', '2233');
