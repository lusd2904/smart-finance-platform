from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint

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


class QuantDailyList(Base):
    """次日策略清单。"""

    __tablename__ = 'quant_daily_list'
    __table_args__ = (
        UniqueConstraint('user_id', 'trade_date', name='uk_daily_list_user_trade'),
        {'comment': '次日策略清单'},
    )

    list_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='清单ID')
    user_id = Column(BigInteger, nullable=False, index=True, comment='所属用户')
    scan_date = Column(Date, nullable=False, comment='扫描日')
    trade_date = Column(Date, nullable=False, comment='下一交易日')
    profile = Column(String(20), nullable=False, server_default="'balanced'", comment='策略档位')
    status = Column(String(16), nullable=False, server_default="'open'", comment='open/empty/skipped')
    auto_enabled = Column(CHAR(1), nullable=False, server_default='0', comment='持续自动交易')
    item_count = Column(Integer, nullable=False, server_default='0', comment='标的数')
    message = Column(String(500), nullable=True, comment='说明')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class QuantDailyListItem(Base):
    """次日策略清单标的。"""

    __tablename__ = 'quant_daily_list_item'
    __table_args__ = (
        UniqueConstraint('user_id', 'symbol', 'market', 'trade_date', 'side', name='uk_daily_item_user_symbol_day'),
        {'comment': '次日策略清单标的'},
    )

    item_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='条目ID')
    list_id = Column(BigInteger, nullable=False, index=True, comment='清单ID')
    user_id = Column(BigInteger, nullable=False, index=True, comment='所属用户')
    trade_date = Column(Date, nullable=False, comment='拟交易日')
    symbol = Column(String(32), nullable=False, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    name = Column(String(64), nullable=True, comment='名称')
    signal = Column('signal', String(8), nullable=False, server_default="'BUY'", comment='信号')
    score = Column(Float, nullable=True, comment='打分')
    confidence = Column(Integer, nullable=True, comment='置信度')
    reason = Column(String(500), nullable=True, comment='理由')
    selected = Column(CHAR(1), nullable=False, server_default='0', comment='勾选')
    auto_trade = Column(CHAR(1), nullable=False, server_default='0', comment='持续自动交易')
    status = Column(String(16), nullable=False, server_default="'listed'", comment='listed/queued/submitted/filled/rejected/skipped')
    side = Column(String(8), nullable=False, server_default="'BUY'", comment='方向')
    quantity = Column(Integer, nullable=True, comment='数量')
    price = Column(Float, nullable=True, comment='参考价')
    order_id = Column(String(64), nullable=True, comment='长桥单号')
    error = Column(String(500), nullable=True, comment='失败原因')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


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
    长桥凭据配置表（按用户一行）
    """

    __tablename__ = 'quant_longbridge_config'
    __table_args__ = (
        UniqueConstraint('user_id', name='uk_quant_longbridge_user'),
        {'comment': '长桥凭据配置表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='配置ID')
    user_id = Column(BigInteger, nullable=False, server_default='1', comment='用户ID')
    app_key = Column(String(255), nullable=True, comment='长桥App Key')
    app_secret = Column(String(255), nullable=True, comment='长桥App Secret')
    access_token = Column(String(2048), nullable=True, comment='长桥Access Token')
    region = Column(String(10), nullable=True, server_default="'cn'", comment='区域（cn/hk等）')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class QuantFactorSnapshot(Base):
    """
    标的因子定时快照（日频）
    """

    __tablename__ = 'quant_factor_snapshot'
    __table_args__ = {'comment': '量化因子定时快照'}

    snapshot_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='快照ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    as_of = Column(String(16), nullable=True, comment='K线截止日期')
    score_total = Column(Float, nullable=True, comment='综合打分')
    risk_level = Column(String(16), nullable=True, comment='风险等级')
    trend_direction = Column(String(16), nullable=True, comment='趋势方向')
    alpha101_count = Column(Integer, nullable=False, server_default='0', comment='Alpha101 个数')
    alpha158_count = Column(Integer, nullable=False, server_default='0', comment='Alpha158 个数')
    score_json = Column(Text, nullable=True, comment='8 大因子族得分 JSON')
    alpha_json = Column(Text, nullable=True, comment='高阶因子 JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='生成时间')


class QuantReadmodelSnapshot(Base):
    """
    读模型聚合快照（资产/持仓/行情/因子总览）
    """

    __tablename__ = 'quant_readmodel_snapshot'
    __table_args__ = {'comment': '读模型聚合快照'}

    snapshot_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='快照ID')
    snapshot_type = Column(String(32), nullable=False, index=True, comment='快照类型 overview/board/factors/positions')
    payload_json = Column(Text, nullable=False, comment='快照 JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='生成时间')


class QuantFactorQc(Base):
    """
    Alphalens 风格因子质检结果（按因子+周期保留最新一条）
    """

    __tablename__ = 'quant_factor_qc'
    __table_args__ = (
        UniqueConstraint('factor_key', 'market', 'horizon', name='uk_factor_qc'),
        {'comment': '量化因子质检（IC/IR/分位收益）'},
    )

    qc_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='质检ID')
    factor_key = Column(String(32), nullable=False, index=True, comment='因子键')
    factor_label = Column(String(64), nullable=True, comment='因子中文名')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    horizon = Column(Integer, nullable=False, server_default='1', comment='前瞻收益天数')
    ic_mean = Column(Float, nullable=True, comment='截面 IC 均值')
    ic_std = Column(Float, nullable=True, comment='截面 IC 标准差')
    ir = Column(Float, nullable=True, comment='信息比率 IC_mean/IC_std')
    spread = Column(Float, nullable=True, comment='分位多空价差百分比')
    sample_dates = Column(Integer, nullable=False, server_default='0', comment='有效 IC 交易日数')
    symbol_count = Column(Integer, nullable=False, server_default='0', comment='截面标的数')
    as_of = Column(String(16), nullable=True, comment='K线截止日期')
    quantile_json = Column(Text, nullable=True, comment='分位收益 JSON')
    payload_json = Column(Text, nullable=True, comment='扩展载荷 JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='生成时间')
