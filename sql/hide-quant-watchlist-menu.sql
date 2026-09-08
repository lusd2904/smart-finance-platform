-- 量化「自选池」并入行情自选后隐藏侧栏入口（权限按钮保留）。
-- visible: 0 显示 / 1 隐藏。可重复执行。

UPDATE sys_menu
SET visible = '1', remark = '已并入 /market/watchlist'
WHERE menu_id = 2203 AND visible <> '1';
