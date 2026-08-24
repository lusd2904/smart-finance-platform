-- 修复行情中心隐藏子页：从列表点入不占侧栏，但路由/API 权限需保留
-- 可重复执行

UPDATE sys_menu
SET visible = '1'
WHERE parent_id = 2100
  AND menu_type = 'C'
  AND path IN ('symbol', 'kline', 'tradingview', 'dashboard', 'coverage');

-- 普通角色补授权（隐藏页不挡接口）
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 2, menu_id
FROM sys_menu
WHERE menu_id IN (2101, 2102, 2111, 2123, 2124);
