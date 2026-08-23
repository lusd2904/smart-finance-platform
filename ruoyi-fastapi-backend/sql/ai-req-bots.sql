-- 需求沟通：可配置多 AI 机器人 + 唯一确定者
-- menu_id 2145-2148。可重复执行。

CREATE TABLE IF NOT EXISTS ai_req_bot (
  bot_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '机器人ID',
  model_id BIGINT NOT NULL COMMENT 'ai_models.model_id',
  display_name VARCHAR(64) NOT NULL COMMENT '群内显示名',
  enabled CHAR(1) NOT NULL DEFAULT '1' COMMENT '是否参与需求沟通',
  is_decider CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否清单确定者',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '发言顺序',
  create_time DATETIME NULL,
  update_time DATETIME NULL,
  PRIMARY KEY (bot_id),
  UNIQUE KEY uk_ai_req_bot_model (model_id),
  KEY ix_ai_req_bot_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='需求沟通AI机器人';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2145 AND 2148;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2145 AND 2148;

INSERT INTO sys_menu VALUES
('2145', 'AI机器人', '4', '5', 'req-bot', 'ai/req-bot/index', '', 'AiReqBotIndex', 1, 0, 'C', '0', '0', 'ai:req:bot', 'peoples', 'admin', sysdate(), '', null, '配置需求沟通参与机器人与清单确定者'),
('2146', '机器人查询', '2145', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:bot', '#', 'admin', sysdate(), '', null, ''),
('2147', '机器人配置', '2145', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:bot:edit', '#', 'admin', sysdate(), '', null, ''),
('2148', '清单确定', '2142', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:edit', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2145'), ('2', '2146'), ('2', '2147'), ('2', '2148');
