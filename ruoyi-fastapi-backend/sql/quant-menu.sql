-- ----------------------------
-- 量化交易 菜单/权限/定时任务
-- 适用库：同 sentiment（智慧金融分析平台）
-- menu_id 使用 2200-2212 段（扩展菜单见 market-feature-extension / feature-extension / deep-feature）
-- ----------------------------

-- 幂等清理（可重复执行）
-- 仅清理本文件基础段 2200-2212，避免误删 2220+ 扩展菜单
delete from sys_role_menu where menu_id between 2200 and 2212;
delete from sys_menu where menu_id between 2200 and 2212;
delete from sys_job where job_id = 102;

-- ----------------------------
-- A. 一级目录：量化交易
-- ----------------------------
insert into sys_menu values('2200', '量化交易', '0', '7', 'quant', null, '', '', 1, 0, 'M', '0', '0', '', 'money', 'admin', sysdate(), '', null, '量化交易目录');

-- ----------------------------
-- B. 二级页面菜单（route_name 与线上一致）
-- ----------------------------
insert into sys_menu values('2201', '因子分析', '2200', '1', 'factor',    'quant/factor/index',    '', 'QuantFactorIndex', 1, 0, 'C', '0', '0', 'quant:factor:schema',   'chart',     'admin', sysdate(), '', null, '因子分析菜单');
insert into sys_menu values('2202', '策略信号', '2200', '2', 'strategy',  'quant/strategy/index',  '', 'QuantStrategyIndex', 1, 0, 'C', '0', '0', 'quant:strategy:run',    'guide',     'admin', sysdate(), '', null, '策略信号菜单');
insert into sys_menu values('2203', '自选池',   '2200', '3', 'watchlist', 'quant/watchlist/index', '', 'QuantWatchlistIndex', 1, 0, 'C', '0', '0', 'quant:watchlist:list',  'star',      'admin', sysdate(), '', null, '自选池菜单');
insert into sys_menu values('2204', '长桥配置', '2200', '4', 'longbridge','quant/longbridge/index','', 'QuantLongbridgeIndex', 1, 0, 'C', '0', '0', 'quant:longbridge:config','edit',     'admin', sysdate(), '', null, '长桥配置菜单');

-- ----------------------------
-- C. 按钮权限
-- ----------------------------
insert into sys_menu values('2205', '因子体系', '2201', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:factor:schema',    '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2206', '因子计算', '2201', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:factor:compute',   '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2207', '运行策略', '2202', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:strategy:run',     '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2208', '策略历史', '2202', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:strategy:history', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2209', '自选新增', '2203', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:watchlist:add',    '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2210', '自选删除', '2203', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:watchlist:remove', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2211', '连接测试', '2204', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:longbridge:test',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2212', '配置保存', '2204', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:longbridge:config','#', 'admin', sysdate(), '', null, '');

-- ----------------------------
-- D. 角色授权：role_id=2 普通角色（admin 为超管无需分配）
-- ----------------------------
insert into sys_role_menu values ('2', '2200');
insert into sys_role_menu values ('2', '2201');
insert into sys_role_menu values ('2', '2202');
insert into sys_role_menu values ('2', '2203');
insert into sys_role_menu values ('2', '2204');
insert into sys_role_menu values ('2', '2205');
insert into sys_role_menu values ('2', '2206');
insert into sys_role_menu values ('2', '2207');
insert into sys_role_menu values ('2', '2208');
insert into sys_role_menu values ('2', '2209');
insert into sys_role_menu values ('2', '2210');
insert into sys_role_menu values ('2', '2211');
insert into sys_role_menu values ('2', '2212');

-- ----------------------------
-- E. 定时任务：每日收盘后运行量化策略（06:00 执行，status '1' 暂停，按需启用）
-- ----------------------------
insert into sys_job values(102, '量化策略每日运行', 'default', 'default', 'module_task.quant_task.run_strategy_job', NULL, NULL, '0 0 6 * * ?', '3', '1', '1', 'admin', sysdate(), '', null, '每日收盘后运行量化策略生成信号');
