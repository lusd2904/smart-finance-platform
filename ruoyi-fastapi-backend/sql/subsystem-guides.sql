-- ----------------------------
-- 各子系统侧栏「使用说明」（C 型页面，order_num=99 置底）
-- menu_id 2701-2706；不使用 2300-2399
-- path=guide → /market/guide、/quant/guide、/trade/guide、/sentiment/guide、/ai/guide、/analysis/guide
-- ----------------------------

-- 幂等清理（可重复执行）
DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2701 AND 2706;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2701 AND 2706;

-- menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, update_by, update_time, remark
insert into sys_menu values('2701', '使用说明', '2100', '99', 'guide', 'guide/index', '', 'MarketGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, '行情中心使用说明');
insert into sys_menu values('2702', '使用说明', '2200', '99', 'guide', 'guide/index', '', 'QuantGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, '量化交易使用说明');
insert into sys_menu values('2703', '使用说明', '2400', '99', 'guide', 'guide/index', '', 'TradeGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, '交易中心使用说明');
insert into sys_menu values('2704', '使用说明', '2000', '99', 'guide', 'guide/index', '', 'SentimentGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, '舆情分析使用说明');
insert into sys_menu values('2705', '使用说明', '4', '99', 'guide', 'guide/index', '', 'AiGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, 'AI 管理使用说明');
insert into sys_menu values('2706', '使用说明', '2500', '99', 'guide', 'guide/index', '', 'AnalysisGuideIndex', 1, 0, 'C', '0', '0', '', 'question', 'admin', sysdate(), '', null, '任务中心使用说明');

-- 角色授权：role_id=2 普通角色（admin 为超管无需分配）
insert into sys_role_menu values ('2', '2701');
insert into sys_role_menu values ('2', '2702');
insert into sys_role_menu values ('2', '2703');
insert into sys_role_menu values ('2', '2704');
insert into sys_role_menu values ('2', '2705');
insert into sys_role_menu values ('2', '2706');
