-- Alpha101 / Alpha158 独立因子值表。禁止再把整包 JSON 塞进 TEXT。
CREATE TABLE IF NOT EXISTS quant_alpha101_value (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  as_of VARCHAR(16) NOT NULL COMMENT 'K线截止日期',
  factor_key VARCHAR(32) NOT NULL COMMENT '因子键（如 alpha001）',
  factor_value DOUBLE NULL COMMENT '因子值',
  create_time DATETIME NULL COMMENT '写入时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_alpha101_symbol_asof_key (symbol, market, as_of, factor_key),
  KEY ix_alpha101_symbol (symbol, market, as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Alpha101 因子值';

CREATE TABLE IF NOT EXISTS quant_alpha158_value (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
  symbol VARCHAR(32) NOT NULL COMMENT '标的代码',
  market VARCHAR(10) NOT NULL DEFAULT 'US' COMMENT '市场',
  as_of VARCHAR(16) NOT NULL COMMENT 'K线截止日期',
  factor_key VARCHAR(32) NOT NULL COMMENT '因子键（如 SUM60）',
  factor_value DOUBLE NULL COMMENT '因子值',
  create_time DATETIME NULL COMMENT '写入时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_alpha158_symbol_asof_key (symbol, market, as_of, factor_key),
  KEY ix_alpha158_symbol (symbol, market, as_of)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Alpha158 因子值';
