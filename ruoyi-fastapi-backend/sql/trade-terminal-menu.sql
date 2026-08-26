-- ----------------------------------------------------
-- 交易中心新增「行情交易」菜单，并为所有系统角色授权
-- ----------------------------------------------------

DELETE FROM sys_role_menu WHERE menu_id = 2430;
DELETE FROM sys_menu WHERE menu_id = 2430;

INSERT INTO sys_menu (
  menu_id, menu_name, parent_id, order_num, path, component,
  query, route_name, is_frame, is_cache, menu_type, visible,
  status, perms, icon, create_by, create_time, update_by,
  update_time, remark
) VALUES (
  2430, '行情交易', 2400, 1, 'terminal', 'market/terminal/index',
  '', 'MarketTerminal', 1, 0, 'C', '0',
  '0', 'trade:terminal:view', 'chart', 'admin', NOW(), '',
  NULL, '专业证券行情与快捷交易终端'
);

-- 为当前系统所有角色（超级管理员、普通角色、业务用户等）赋予行情交易菜单权限
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT role_id, 2430 FROM sys_role;

-- 确保交易中心顶级目录（2400）也包含在角色权限中
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT role_id, 2400 FROM sys_role;

