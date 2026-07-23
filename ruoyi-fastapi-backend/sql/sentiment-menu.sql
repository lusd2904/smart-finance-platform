-- ----------------------------
-- 舆情AI分析子系统 菜单/权限/定时任务
-- 适用库：sentiment-ai
-- menu_id 使用 2000-2009 段（现库业务段未占用，框架 auto_increment=2000 预留）
-- ----------------------------

-- 幂等清理（可重复执行）
delete from sys_role_menu where menu_id between 2000 and 2009;
delete from sys_menu where menu_id between 2000 and 2009;
delete from sys_job where job_id = 100;

-- ----------------------------
-- A. 一级目录：舆情分析
-- ----------------------------
insert into sys_menu values('2000', '舆情分析', '0', '5', 'sentiment', null, '', '', 1, 0, 'M', '0', '0', '', 'chart', 'admin', sysdate(), '', null, '舆情分析目录');

-- ----------------------------
-- B. 二级页面菜单（route_name 与线上一致，避免与行情 dashboard 冲突）
-- ----------------------------
insert into sys_menu values('2001', '舆情大盘', '2000', '1', 'dashboard', 'sentiment/dashboard/index', '', 'SentimentDashboardIndex', 1, 0, 'C', '0', '0', 'sentiment:news:list',     'dashboard', 'admin', sysdate(), '', null, '舆情大盘菜单');
insert into sys_menu values('2002', '资讯列表', '2000', '2', 'news',      'sentiment/news/index',      '', 'SentimentNewsIndex', 1, 0, 'C', '0', '0', 'sentiment:news:list',     'documentation', 'admin', sysdate(), '', null, '资讯列表菜单');
insert into sys_menu values('2003', '分析历史', '2000', '3', 'analysis',  'sentiment/analysis/index',  '', 'SentimentAnalysisIndex', 1, 0, 'C', '0', '0', 'sentiment:analysis:list', 'time-range', 'admin', sysdate(), '', null, '分析历史菜单');
insert into sys_menu values('2004', 'AI配置',   '2000', '4', 'config',    'sentiment/config/index',    '', 'SentimentConfigIndex', 1, 0, 'C', '0', '0', 'sentiment:config:query',  'edit', 'admin', sysdate(), '', null, 'AI配置菜单');

-- ----------------------------
-- C. 按钮权限
-- ----------------------------
insert into sys_menu values('2005', '舆情采集', '2002', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'sentiment:news:collect',    '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2006', '资讯删除', '2002', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'sentiment:news:remove',     '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2007', '执行分析', '2003', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'sentiment:analysis:run',    '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2008', '分析详情', '2003', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'sentiment:analysis:query',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2009', '配置保存', '2004', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'sentiment:config:edit',     '#', 'admin', sysdate(), '', null, '');

-- ----------------------------
-- D. 角色授权：role_id=2 普通角色（admin 为超管无需分配）
-- ----------------------------
insert into sys_role_menu values ('2', '2000');
insert into sys_role_menu values ('2', '2001');
insert into sys_role_menu values ('2', '2002');
insert into sys_role_menu values ('2', '2003');
insert into sys_role_menu values ('2', '2004');
insert into sys_role_menu values ('2', '2005');
insert into sys_role_menu values ('2', '2006');
insert into sys_role_menu values ('2', '2007');
insert into sys_role_menu values ('2', '2008');
insert into sys_role_menu values ('2', '2009');

-- ----------------------------
-- E. 定时任务：每10分钟舆情采集与AI分析（status '0' 启用）
-- ----------------------------
insert into sys_job values(100, '舆情采集与AI分析', 'default', 'default', 'module_task.sentiment_task.collect_and_analyze_job', NULL, NULL, '0 0/10 * * * ?', '3', '1', '0', 'admin', sysdate(), '', null, '每10分钟执行舆情采集与AI分析');
