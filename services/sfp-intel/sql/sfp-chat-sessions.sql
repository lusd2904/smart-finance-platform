-- Go-native AI chat session store (sfp-intel). Idempotent.
CREATE TABLE IF NOT EXISTS sfp_chat_session (
  session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
  user_id BIGINT NOT NULL COMMENT '用户ID',
  title VARCHAR(200) NULL COMMENT '标题',
  agent_data JSON NULL COMMENT '智能体数据',
  session_data JSON NULL COMMENT '会话数据',
  created_at DATETIME NULL COMMENT '创建时间',
  updated_at DATETIME NULL COMMENT '更新时间',
  PRIMARY KEY (session_id),
  KEY ix_sfp_chat_session_user (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Go AI对话会话';

CREATE TABLE IF NOT EXISTS sfp_chat_message (
  message_id VARCHAR(64) NOT NULL COMMENT '消息ID',
  session_id VARCHAR(64) NOT NULL COMMENT '会话ID',
  role VARCHAR(32) NOT NULL COMMENT '角色',
  content MEDIUMTEXT NULL COMMENT '内容',
  reasoning_content MEDIUMTEXT NULL COMMENT '推理内容',
  images JSON NULL COMMENT '图片',
  metrics JSON NULL COMMENT '指标',
  from_history TINYINT NOT NULL DEFAULT 0 COMMENT '是否来自历史',
  created_at DATETIME NULL COMMENT '创建时间',
  PRIMARY KEY (message_id),
  KEY ix_sfp_chat_message_session (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Go AI对话消息';
