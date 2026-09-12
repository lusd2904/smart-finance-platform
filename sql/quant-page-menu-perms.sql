-- Align C-page sys_menu.perms with the Go routes those pages call on mount.
-- Live hub already has this; script is so main / compose seeds do not revert.
--
--   2201 因子分析 (C): quant:factor:schema → quant:factor:list
--        GET /quant/factor/schema requires quant:factor:list
--   2202 策略信号 (C): quant:strategy:run → quant:strategy:history
--        GET /quant/strategy/history on mount requires quant:strategy:history
--
-- F buttons 2205 / 2206 / 2207 / 2208 are left unchanged.
-- Idempotent: UPDATE only when perms still differ. No JWT / cookie / HttpOnly changes.

UPDATE sys_menu
SET perms = 'quant:factor:list',
    update_by = 'admin',
    update_time = sysdate()
WHERE menu_id = 2201
  AND menu_type = 'C'
  AND IFNULL(perms, '') <> 'quant:factor:list';

UPDATE sys_menu
SET perms = 'quant:strategy:history',
    update_by = 'admin',
    update_time = sysdate()
WHERE menu_id = 2202
  AND menu_type = 'C'
  AND IFNULL(perms, '') <> 'quant:strategy:history';
