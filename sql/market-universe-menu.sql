-- 行情中心侧栏增加「全部股票」（可重复执行）
-- 复用已有 /market/stocks 路由（menu_id 2120），改为侧栏可见。
-- 新库执行 market-menu-unify.sql 即可；已有库补跑本文件。

UPDATE sys_menu
SET visible = '0',
    menu_name = '全部股票',
    order_num = 2,
    icon = 'list',
    remark = '三市场全量代码分页列表'
WHERE parent_id = 2100 AND path = 'stocks' AND menu_type = 'C';

UPDATE sys_menu
SET order_num = 3, remark = '精选标的报价入口，可点入 K 线/详情'
WHERE parent_id = 2100 AND path = 'board' AND menu_type = 'C';

UPDATE sys_menu
SET order_num = 4
WHERE parent_id = 2100 AND path = 'watchlist' AND menu_type = 'C';

UPDATE sys_menu
SET order_num = 5
WHERE parent_id = 2100 AND path = 'finance-news' AND menu_type = 'C';

UPDATE sys_menu
SET order_num = 6
WHERE parent_id = 2100 AND path = 'ai-workbench' AND menu_type = 'C';
