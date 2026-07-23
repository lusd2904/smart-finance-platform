-- ============================================================
-- AI连接配置统一改造迁移脚本
-- 目的：
--   1. 给 ai_models 增加 scope 字段，用于区分连接配置的适用范围
--      (chat=AI助手 / sentiment=舆情模块 / quant=量化模块预留 / global=全局复用)
--   2. sentiment_ai_config 表瘦身：AI连接凭据(base_url/api_key/model_name/temperature)
--      不再作为数据来源，改由 ai_models(scope='sentiment') 提供；这几列保留但标注废弃，
--      不做物理删除，避免影响任何仍可能引用这些列的历史代码或数据。
-- 幂等性：可重复执行不报错。
--   注意：本机 MySQL 9.4.0 (Homebrew) 实测不支持
--   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` 语法（PREPARE前直接报1064语法错误，
--   已用最小复现验证），因此改用 information_schema 探测 + PREPARE/EXECUTE 动态SQL
--   来实现"仅在列不存在时才新增"的条件DDL，这是纯SQL文件（无存储过程）下的标准写法。
-- ============================================================

-- 1. ai_models 增加 scope 字段（条件新增，幂等）
SET @col_exists = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_models' AND COLUMN_NAME = 'scope'
);
SET @ddl = IF(
    @col_exists = 0,
    'ALTER TABLE `ai_models` ADD COLUMN `scope` VARCHAR(32) NOT NULL DEFAULT ''chat'' COMMENT ''适用范围(chat=AI助手/sentiment=舆情模块/quant=量化模块预留/global=全局复用)'' AFTER `model_sort`',
    'SELECT ''ai_models.scope already exists, skip'' AS info'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 保险起见统一订正列注释（无论新增还是已存在，都确保注释内容正确一致；MODIFY COLUMN本身可重复执行）
ALTER TABLE `ai_models`
    MODIFY COLUMN `scope` VARCHAR(32) NOT NULL DEFAULT 'chat'
    COMMENT '适用范围(chat=AI助手/sentiment=舆情模块/quant=量化模块预留/global=全局复用)';

-- 回填历史数据（新增列已有DEFAULT 'chat'自动回填，此语句仅作为幂等保险，避免历史脏数据遗漏）
UPDATE `ai_models` SET `scope` = 'chat' WHERE `scope` IS NULL OR `scope` = '';

-- 2. sentiment_ai_config 表瘦身：标注废弃列（不删除、不改变类型，只更新列注释）
-- MODIFY COLUMN 天然幂等：多次执行结果一致，无需条件判断。
ALTER TABLE `sentiment_ai_config`
    MODIFY COLUMN `base_url` VARCHAR(255) NULL
    COMMENT '[已废弃]AI接口Base URL，请改用ai_models(scope=sentiment).base_url';

ALTER TABLE `sentiment_ai_config`
    MODIFY COLUMN `api_key` VARCHAR(255) NULL
    COMMENT '[已废弃]AI接口API Key，请改用ai_models(scope=sentiment).api_key';

ALTER TABLE `sentiment_ai_config`
    MODIFY COLUMN `model_name` VARCHAR(100) NULL
    COMMENT '[已废弃]模型名称，请改用ai_models(scope=sentiment).model_code';

ALTER TABLE `sentiment_ai_config`
    MODIFY COLUMN `temperature` FLOAT NULL DEFAULT 0.2
    COMMENT '[已废弃]温度，请改用ai_models(scope=sentiment).temperature';
