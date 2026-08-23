-- 行情中心侧栏整合（可重复执行）
-- 侧栏：市场热度 / 全部股票 / 智能选股 / 行情台 / 自选清单 / 财经资讯 / AI研判。
-- 详情 / K 线 / 高级图等从列表点入，路由仍保留（visible=1 隐藏侧栏）。
-- 按 parent_id + path 更新，兼容热度菜单 2140 或 2600。

UPDATE sys_menu
SET menu_name = '行情中心',
    order_num = 2,
    remark = '行情中心目录'
WHERE menu_id = 2100;

-- 侧栏保留
UPDATE sys_menu
SET visible = '0', menu_name = '市场热度', order_num = 1, remark = '三市场热度与 Top50'
WHERE parent_id = 2100 AND path = 'heat' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = '全部股票', order_num = 2, icon = 'list',
    remark = '三市场全量代码分页列表'
WHERE parent_id = 2100 AND path = 'stocks' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = '智能选股', order_num = 3, icon = 'star',
    perms = 'market:picks:list', remark = '指标+舆情+开盘指数，休市去掉指数'
WHERE parent_id = 2100 AND path = 'recommendations' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = '行情台', order_num = 4, remark = '精选标的报价入口，可点入 K 线/详情'
WHERE parent_id = 2100 AND path = 'board' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = '自选清单', order_num = 5, remark = '行情中心自选与小时综合分析'
WHERE parent_id = 2100 AND path = 'watchlist' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = '财经资讯', order_num = 6, remark = '财经资讯简报流'
WHERE parent_id = 2100 AND path = 'finance-news' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '0', menu_name = 'AI研判', order_num = 7, remark = '单标的与批量研判'
WHERE parent_id = 2100 AND path = 'ai-workbench' AND menu_type = 'C';

-- 列表点入的二级页：隐藏侧栏，保留路由
UPDATE sys_menu
SET visible = '1', order_num = 21, remark = '从行情台/自选点入，不单独占侧栏'
WHERE parent_id = 2100 AND path = 'kline' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '1', order_num = 22, remark = '与行情台重叠，不单独占侧栏'
WHERE parent_id = 2100 AND path = 'dashboard' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '1', order_num = 23, remark = '标的详情，从列表点入'
WHERE parent_id = 2100 AND path = 'symbol' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '1', order_num = 24, remark = '与行情台重叠，不单独占侧栏'
WHERE parent_id = 2100 AND path = 'stock-pool' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '1', order_num = 27, remark = '覆盖检测从行情台进入，不单独占侧栏'
WHERE parent_id = 2100 AND path = 'coverage' AND menu_type = 'C';

UPDATE sys_menu
SET visible = '1', order_num = 28, remark = '高级图从 K 线/覆盖点入，不单独占侧栏'
WHERE parent_id = 2100 AND path = 'tradingview' AND menu_type = 'C';
