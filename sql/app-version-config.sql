-- M5 发布工程：客户端版本检查基线（sys_config）。
-- 可重复执行（INSERT ... SELECT WHERE NOT EXISTS）。
-- 管理员后续在 Web「系统设置-参数设置」中直接修改即可，无需改代码。
--
-- 键名约定：app.version.{platform}.{latest|min|url|notes}
--   latest：最新发布版本（点分数字）
--   min   ：低于此版本强制升级（可缺省 = 全部可选升级）
--   url   ：下载地址（Android 直装 APK；桌面为安装包页）
--   notes ：升级说明
--
-- ⚠️ 占位 URL 需替换为真实分发地址后生效；
--    sys_config 有启动缓存，改动后通过参数设置页面保存会自动刷新缓存，
--    直接执行本 SQL 则需重启后端或在页面内任意保存一次配置触发重载。

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端安卓最新版本', 'app.version.android.latest', '1.0.0', 'Y', 'admin', NOW(), 'M5 版本检查基线'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.android.latest');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端安卓最低可用版本', 'app.version.android.min', '0.0.0', 'Y', 'admin', NOW(), '低于此版本强制升级；0.0.0 表示全部可选'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.android.min');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端安卓下载地址', 'app.version.android.url', '', 'Y', 'admin', NOW(), '直装 APK 分发地址（占位，需替换）'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.android.url');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端安卓升级说明', 'app.version.android.notes', '', 'Y', 'admin', NOW(), ''
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.android.notes');

-- iOS（TestFlight 分发，url 留空由 App Store 接管）
INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端iOS最新版本', 'app.version.ios.latest', '1.0.0', 'Y', 'admin', NOW(), 'M5 版本检查基线'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.ios.latest');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端iOS最低可用版本', 'app.version.ios.min', '0.0.0', 'Y', 'admin', NOW(), ''
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.ios.min');

-- macOS（dmg 直装）
INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端macOS最新版本', 'app.version.macos.latest', '1.0.0', 'Y', 'admin', NOW(), 'M5 版本检查基线'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.macos.latest');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端macOS下载地址', 'app.version.macos.url', '', 'Y', 'admin', NOW(), 'dmg 分发地址（占位，需替换）'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.macos.url');

-- Windows（exe 压包直装）
INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端Windows最新版本', 'app.version.windows.latest', '1.0.0', 'Y', 'admin', NOW(), 'M5 版本检查基线'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.windows.latest');

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
SELECT '客户端Windows下载地址', 'app.version.windows.url', '', 'Y', 'admin', NOW(), '安装包分发地址（占位，需替换）'
WHERE NOT EXISTS (SELECT 1 FROM sys_config WHERE config_key = 'app.version.windows.url');
