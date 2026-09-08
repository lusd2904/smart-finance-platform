-- AI 需求沟通群 + 需求清单
-- menu_id 2140-2146
-- 可重复执行。

CREATE TABLE IF NOT EXISTS ai_req_message (
  msg_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  room_id INT NOT NULL DEFAULT 1 COMMENT '房间ID',
  user_id BIGINT NOT NULL COMMENT '发送人，0 为 Grok',
  user_name VARCHAR(64) NOT NULL COMMENT '账号',
  nick_name VARCHAR(64) NULL COMMENT '昵称',
  role VARCHAR(16) NOT NULL DEFAULT 'user' COMMENT 'user/ai/system',
  content TEXT NOT NULL COMMENT '正文',
  create_time DATETIME NULL COMMENT '发送时间',
  PRIMARY KEY (msg_id),
  KEY ix_req_msg_room_id (room_id, msg_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI需求沟通群聊消息';

CREATE TABLE IF NOT EXISTS ai_req_item (
  item_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '需求ID',
  title VARCHAR(200) NOT NULL COMMENT '标题',
  detail TEXT NULL COMMENT '说明',
  priority VARCHAR(8) NULL DEFAULT 'P2' COMMENT 'P1/P2/P3',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/developing/testing/done/cancelled',
  source_msg_id BIGINT NULL COMMENT '来源消息',
  created_by BIGINT NULL COMMENT '创建人',
  created_by_name VARCHAR(64) NULL COMMENT '创建人名称',
  remark VARCHAR(500) NULL COMMENT '备注',
  create_time DATETIME NULL COMMENT '创建时间',
  update_time DATETIME NULL COMMENT '更新时间',
  PRIMARY KEY (item_id),
  KEY ix_req_item_status (status),
  KEY ix_req_item_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI需求清单';

DELETE FROM sys_role_menu WHERE menu_id BETWEEN 2140 AND 2146;
DELETE FROM sys_menu WHERE menu_id BETWEEN 2140 AND 2146;

INSERT INTO sys_menu VALUES
('2140', '需求沟通', '4', '3', 'req-chat', 'ai/req-chat/index', '', 'AiReqChatIndex', 1, 0, 'C', '0', '0', 'ai:req:chat', 'wechat', 'admin', sysdate(), '', null, '排除 admin/niangao 的需求讨论群，固定 Grok'),
('2141', '发送消息', '2140', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:chat', '#', 'admin', sysdate(), '', null, ''),
('2142', 'AI需求清单', '4', '4', 'req-list', 'ai/req-list/index', '', 'AiReqListIndex', 1, 0, 'C', '0', '0', 'ai:req:list', 'list', 'admin', sysdate(), '', null, '已确认优化点，开发测试后手动改状态'),
('2143', '清单查询', '2142', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:list', '#', 'admin', sysdate(), '', null, ''),
('2144', '状态更新', '2142', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'ai:req:edit', '#', 'admin', sysdate(), '', null, '');

INSERT INTO sys_role_menu VALUES
('2', '2140'), ('2', '2141'), ('2', '2142'), ('2', '2143'), ('2', '2144');
