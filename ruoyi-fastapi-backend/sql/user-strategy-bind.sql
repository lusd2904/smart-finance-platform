-- 登录账户绑定的生效策略档位（与 plat_strategy_profile_user 权重覆盖分离）。
-- 定时策略运行 / 自动交易 / 次日清单默认用该档，未绑定则 balanced。
CREATE TABLE IF NOT EXISTS plat_user_strategy_bind (
  user_id BIGINT NOT NULL COMMENT '用户ID',
  profile_code VARCHAR(32) NOT NULL DEFAULT 'balanced' COMMENT '生效策略编码 conservative/balanced/aggressive',
  update_time DATETIME DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户生效策略绑定';
