-- 次日策略清单对业务角色开放；交易开关仍在策略配置，按登录账户生效。
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT r.role_id, m.menu_id
FROM sys_role r
CROSS JOIN (
  SELECT 2235 AS menu_id
  UNION ALL SELECT 2236
  UNION ALL SELECT 2237
  UNION ALL SELECT 2238
  UNION ALL SELECT 2239
) m
WHERE r.role_id <> 1
  AND r.status = '0';
