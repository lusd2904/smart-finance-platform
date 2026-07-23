from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Float, Integer, String, Text

from config.database import Base


class QuantStrategyRun(Base):
    """
    量化策略运行记录表
    """

    __tablename__ = 'quant_strategy_run'
    __table_args__ = {'comment': '量化策略运行记录表'}

    run_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='运行ID')
    cycle_id = Column(String(64), nullable=True, index=True, comment='批次ID')
    strategy_profile = Column(String(20), nullable=False, server_default="'balanced'", comment='策略档位')
    symbols_count = Column(Integer, nullable=False, server_default='0', comment='参与标的数')
    signal_count = Column(Integer, nullable=False, server_default='0', comment='产出信号数')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='运行时间')


class QuantStrategySignal(Base):
    """
    量化策略信号表
    """

    __tablename__ = 'quant_strategy_signal'
    __table_args__ = {'comment': '量化策略信号表'}

    signal_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='信号ID')
    run_id = Column(BigInteger, nullable=False, index=True, comment='所属运行ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    signal = Column(String(8), nullable=False, server_default="'HOLD'", comment='信号（BUY/HOLD/SELL）')
    score = Column(Float, nullable=True, comment='综合打分（0-100）')
    confidence = Column(Integer, nullable=True, comment='置信度（0-100）')
    reason = Column(String(500), nullable=True, comment='信号理由')
    factor_json = Column(Text, nullable=True, comment='因子明细JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='生成时间')


class QuantWatchlist(Base):
    """
    量化自选池表
    """

    __tablename__ = 'quant_watchlist'
    __table_args__ = {'comment': '量化自选池表'}

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场（US/HK/CN）')
    note = Column(String(255), nullable=True, comment='备注')
    enabled = Column(CHAR(1), nullable=False, server_default='1', comment='是否启用（0否 1是）')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='加入时间')


class QuantLongbridgeConfig(Base):
    """
    长桥凭据配置表
    """

    __tablename__ = 'quant_longbridge_config'
    __table_args__ = {'comment': '长桥凭据配置表'}

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='配置ID')
    app_key = Column(String(255), nullable=True, comment='长桥App Key')
    app_secret = Column(String(255), nullable=True, comment='长桥App Secret')
    access_token = Column(String(512), nullable=True, comment='长桥Access Token')
    region = Column(String(10), nullable=True, server_default="'cn'", comment='区域（cn/hk等）')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')
