-- A股资金与事件看板：板块资金流 / 涨停池 / 龙虎榜 / 宏观日历
-- menu_id 2610-2612（避开 2600-2602 热度）

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2610 AND 2611;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2610 AND 2611;

INSERT INTO sys_menu VALUES
('2610', '资金与日历', '2100', '6', 'flow', 'market/flow/index', '', 'MarketFlowBoard', 1, 0, 'C', '0', '0', 'market:flow:list', 'money', 'admin', sysdate(), '', null, '板块资金、涨停、龙虎榜与宏观/财报日历'),
('2611', '资金查询', '2610', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:flow:list', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES ('2', '2610'), ('2', '2611');
