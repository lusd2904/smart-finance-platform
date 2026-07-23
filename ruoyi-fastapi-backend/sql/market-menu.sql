-- ----------------------------
-- 行情数据中心 菜单/权限/定时任务
-- 适用库：同 sentiment（智慧金融分析平台）
-- menu_id 使用 2100-2107 段（扩展菜单见 market-feature-extension / feature-extension / full-feature / deep-feature）
-- ----------------------------

-- 幂等清理（可重复执行）
-- 仅清理本文件基础段 2100-2107，避免误删 2110+ 扩展菜单
delete from sys_role_menu where menu_id between 2100 and 2107;
delete from sys_menu where menu_id between 2100 and 2107;
delete from sys_job where job_id = 101;

-- ----------------------------
-- A. 一级目录：行情数据中心
-- ----------------------------
insert into sys_menu values('2100', '行情数据中心', '0', '6', 'market', null, '', '', 1, 0, 'M', '0', '0', '', 'chart', 'admin', sysdate(), '', null, '行情数据中心目录');

-- ----------------------------
-- B. 二级页面菜单（route_name 与线上一致，避免与舆情 dashboard 冲突）
-- ----------------------------
insert into sys_menu values('2101', '行情K线', '2100', '1', 'kline',     'market/kline/index',     '', 'MarketKlineIndex', 1, 0, 'C', '0', '0', 'market:kline:list',      'chart',     'admin', sysdate(), '', null, '行情K线菜单');
insert into sys_menu values('2102', '行情概览', '2100', '2', 'dashboard', 'market/dashboard/index', '', 'MarketDashboardIndex', 1, 0, 'C', '0', '0', 'market:instrument:list', 'dashboard', 'admin', sysdate(), '', null, '行情概览菜单');

-- ----------------------------
-- C. 按钮权限
-- ----------------------------
insert into sys_menu values('2103', '标的列表', '2101', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:instrument:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2104', 'K线查询', '2101', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:kline:list',      '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2105', '指标查询', '2101', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:indicators:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2106', '手动同步', '2101', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:sync',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2107', 'AI研判',  '2101', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:ai:analyze',      '#', 'admin', sysdate(), '', null, '');

-- ----------------------------
-- D. 角色授权：role_id=2 普通角色（admin 为超管无需分配）
-- ----------------------------
insert into sys_role_menu values ('2', '2100');
insert into sys_role_menu values ('2', '2101');
insert into sys_role_menu values ('2', '2102');
insert into sys_role_menu values ('2', '2103');
insert into sys_role_menu values ('2', '2104');
insert into sys_role_menu values ('2', '2105');
insert into sys_role_menu values ('2', '2106');
insert into sys_role_menu values ('2', '2107');

-- ----------------------------
-- E. 定时任务：每日收盘后同步行情（05:30 执行，status '0' 启用）
-- ----------------------------
insert into sys_job values(101, '行情数据每日同步', 'default', 'default', 'module_task.market_task.sync_market_job', NULL, NULL, '0 30 5 * * ?', '3', '1', '0', 'admin', sysdate(), '', null, '每日收盘后同步行情数据与技术指标');
