-- 交易工作台：自选 / K线 / 盘口 / 快捷交易 / 量化 / AI
INSERT INTO sys_menu (
  menu_id, menu_name, parent_id, order_num, path, component, query, route_name,
  is_frame, is_cache, menu_type, visible, status, perms, icon,
  create_by, create_time, update_by, update_time, remark
) SELECT
  2429, '交易工作台', 2400, 0, 'desk', 'trade/desk/index', '', 'TradeDeskIndex',
  1, 0, 'C', '0', '0', 'trade:order:submit', 'guide',
  'admin', sysdate(), '', null, '自选+K线+盘口+快捷交易+量化+AI'
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_id = 2429);

INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, 2429 FROM sys_role r WHERE r.role_id <> 1 AND r.status = '0';
