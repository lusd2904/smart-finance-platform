-- 登录账户自己的策略档位覆盖。系统默认仍在 plat_strategy_profile。
CREATE TABLE IF NOT EXISTS plat_strategy_profile_user (
  user_id BIGINT NOT NULL COMMENT '用户ID',
  profile_code VARCHAR(32) NOT NULL COMMENT '策略编码',
  profile_name VARCHAR(64) NOT NULL COMMENT '策略名称',
  config_json TEXT NOT NULL COMMENT '配置JSON',
  update_time DATETIME DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (user_id, profile_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户策略档位覆盖';
