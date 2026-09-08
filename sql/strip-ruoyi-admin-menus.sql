-- 剥离 RuoYi 管理台冗余菜单，仅保留用户/角色/菜单（IAM）与 SFP 业务菜单。
-- 适用已有库：在业务低峰执行；执行后请让在线用户重新登录以刷新 getRouters 缓存。

-- 1) 解除角色-菜单关联
DELETE FROM sys_role_menu
WHERE menu_id IN (
  SELECT menu_id FROM sys_menu
  WHERE menu_id IN ('2','3','103','104','105','106','107','108','109','110','111','112','113','114','115','116','117','120','500','501')
     OR parent_id IN ('2','3','108','103','104','105','106','107')
     OR menu_id BETWEEN 1016 AND 1060
);

-- 2) 删除按钮权限与子菜单
DELETE FROM sys_menu
WHERE menu_id BETWEEN 1016 AND 1060;

DELETE FROM sys_menu
WHERE menu_id IN ('500','501','109','110','111','112','113','114','115','116','117','120');

DELETE FROM sys_menu
WHERE menu_id IN ('103','104','105','106','107','108');

DELETE FROM sys_menu
WHERE menu_id IN ('2','3');
