-- ----------------------------
-- 行情/量化功能扩展：财经资讯、标的详情、扫描台账、内容缓存
-- menu_id 使用 2110-2119（market 扩展）与 2220-2229（quant 扩展）
-- 表结构由应用启动 create_all 自动创建；本脚本主要注册菜单/权限/定时任务
-- 适用库：同 sentiment（智慧金融分析平台）
-- ----------------------------

-- 幂等清理扩展菜单（精确到本文件 ID，避免误删 2130/2131 股票池推荐 与 2225 策略配置 等）
delete from sys_role_menu where menu_id between 2110 and 2114;
delete from sys_role_menu where menu_id between 2220 and 2223;
delete from sys_menu where menu_id between 2110 and 2114;
delete from sys_menu where menu_id between 2220 and 2223;
delete from sys_job where job_id in (103, 104);

-- ----------------------------
-- A. 行情扩展页面
-- ----------------------------
insert into sys_menu values('2110', '财经资讯', '2100', '3', 'finance-news', 'market/finance-news/index', '', 'MarketFinanceNewsIndex', 1, 0, 'C', '0', '0', 'market:finance:list', 'documentation', 'admin', sysdate(), '', null, '财经资讯简报流');
insert into sys_menu values('2111', '标的详情', '2100', '4', 'symbol', 'market/symbol/index', '', 'MarketSymbolIndex', 1, 0, 'C', '0', '0', 'market:symbol:overview', 'list', 'admin', sysdate(), '', null, '标的详情页');

-- 按钮权限
insert into sys_menu values('2112', '简报查询', '2110', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:finance:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2113', '详情概览', '2111', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:symbol:overview', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2114', '内容缓存', '2111', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'market:symbol:content', '#', 'admin', sysdate(), '', null, '');

-- 角色授权 role_id=2
insert into sys_role_menu values ('2', '2110');
insert into sys_role_menu values ('2', '2111');
insert into sys_role_menu values ('2', '2112');
insert into sys_role_menu values ('2', '2113');
insert into sys_role_menu values ('2', '2114');

-- ----------------------------
-- B. 量化扩展页面
-- ----------------------------
insert into sys_menu values('2220', '扫描台账', '2200', '5', 'scan-runs', 'quant/scan-runs/index', '', 'QuantScanRunsIndex', 1, 0, 'C', '0', '0', 'quant:scan:list', 'log', 'admin', sysdate(), '', null, '策略扫描运行台账');
insert into sys_menu values('2221', '扫描结果', '2200', '6', 'scan-result', 'quant/scan-result/index', '', 'QuantScanResultIndex', 1, 1, 'C', '0', '0', 'quant:scan:query', 'eye-open', 'admin', sysdate(), '', null, '单标的扫描结果（可隐藏）');

insert into sys_menu values('2222', '台账列表', '2220', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:scan:list', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('2223', '台账详情', '2220', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'quant:scan:query', '#', 'admin', sysdate(), '', null, '');

insert into sys_role_menu values ('2', '2220');
insert into sys_role_menu values ('2', '2221');
insert into sys_role_menu values ('2', '2222');
insert into sys_role_menu values ('2', '2223');

-- ----------------------------
-- C. 定时任务
-- ----------------------------
-- 财经资讯刷新：每小时
insert into sys_job values(103, '财经资讯简报刷新', 'default', 'default', 'module_task.market_task.refresh_finance_briefings_job', NULL, NULL, '0 15 * * * ?', '3', '1', '0', 'admin', sysdate(), '', null, '聚合内部简报与外部新闻写入 finance_briefing');
-- 热门标的内容缓存：每30分钟（默认暂停，需长桥凭据后启用）
insert into sys_job values(104, '标的内容缓存刷新', 'default', 'default', 'module_task.market_task.refresh_symbol_content_job', NULL, NULL, '0 0/30 * * * ?', '3', '1', '1', 'admin', sysdate(), '', null, '长桥公告/资讯/讨论缓存，凭据配置后启用');
