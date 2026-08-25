from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Float, Integer, Numeric, String, Text

from config.database import Base


class PlatRiskRule(Base):
    """
    风控规则表
    """

    __tablename__ = 'plat_risk_rule'
    __table_args__ = {'comment': '风控规则表'}

    rule_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='规则ID')
    rule_name = Column(String(100), nullable=False, comment='规则名称')
    rule_type = Column(String(32), nullable=False, server_default="'position'", comment='规则类型')
    symbol = Column(String(32), nullable=True, comment='关联标的代码')
    threshold = Column(Float, nullable=True, comment='阈值')
    enabled = Column(CHAR(1), nullable=False, server_default='1', comment='是否启用（0否 1是）')
    remark = Column(String(500), nullable=True, comment='备注')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PlatRiskEvent(Base):
    """
    风控触发事件表
    """

    __tablename__ = 'plat_risk_event'
    __table_args__ = {'comment': '风控触发事件表'}

    event_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='事件ID')
    rule_id = Column(BigInteger, nullable=True, comment='关联规则ID')
    event_level = Column(String(16), nullable=False, server_default="'warn'", comment='事件等级')
    title = Column(String(200), nullable=False, comment='事件标题')
    content = Column(String(1000), nullable=True, comment='事件详情')
    symbol = Column(String(32), nullable=True, comment='标的代码')
    handled = Column(CHAR(1), nullable=False, server_default='0', comment='是否已处理（0否 1是，兼容旧字段）')
    review_status = Column(
        String(32),
        nullable=False,
        server_default="'pending_review'",
        comment='复核状态(pending_review/confirmed/ignored/need_review/overdue)',
    )
    handle_remark = Column(String(500), nullable=True, comment='处理备注')
    handled_by = Column(String(64), nullable=True, comment='处理人')
    handle_time = Column(DateTime, nullable=True, comment='处理时间')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='触发时间')


class PlatStrategyProfile(Base):
    """
    策略配置档位表
    """

    __tablename__ = 'plat_strategy_profile'
    __table_args__ = {'comment': '策略配置档位表'}

    profile_code = Column(String(32), primary_key=True, nullable=False, comment='策略编码')
    profile_name = Column(String(64), nullable=False, comment='策略名称')
    config_json = Column(Text, nullable=False, comment='配置JSON')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PlatStrategyProfileUser(Base):
    """登录账户自己的策略档位覆盖，不影响其他账户。"""

    __tablename__ = 'plat_strategy_profile_user'
    __table_args__ = {'comment': '用户策略档位覆盖'}

    user_id = Column(BigInteger, primary_key=True, nullable=False, comment='用户ID')
    profile_code = Column(String(32), primary_key=True, nullable=False, comment='策略编码')
    profile_name = Column(String(64), nullable=False, comment='策略名称')
    config_json = Column(Text, nullable=False, comment='配置JSON')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class PlatFeishuSubscription(Base):
    """飞书策略摘要订阅。"""

    __tablename__ = 'plat_feishu_subscription'
    __table_args__ = {'comment': '飞书策略摘要订阅'}

    sub_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='订阅ID')
    user_id = Column(BigInteger, nullable=False, unique=True, comment='用户ID')
    personal_enabled = Column(CHAR(1), nullable=False, server_default='0', comment='个人会话')
    group_enabled = Column(CHAR(1), nullable=False, server_default='0', comment='群')
    personal_webhook = Column(String(500), nullable=True, comment='个人 Webhook')
    group_webhook = Column(String(500), nullable=True, comment='群 Webhook')
    push_time = Column(String(8), nullable=False, server_default="'18:30'", comment='推送时刻')
    timezone = Column(String(64), nullable=False, server_default="'Asia/Shanghai'", comment='时区')
    last_personal_key = Column(String(64), nullable=True, comment='个人去重键')
    last_group_key = Column(String(64), nullable=True, comment='群去重键')
    last_error = Column(String(500), nullable=True, comment='最近错误')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class PlatNotification(Base):
    """
    系统通知表
    """

    __tablename__ = 'plat_notification'
    __table_args__ = {'comment': '系统通知表'}

    notice_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='通知ID')
    title = Column(String(200), nullable=False, comment='标题')
    content = Column(String(2000), nullable=True, comment='内容')
    level = Column(String(16), nullable=False, server_default="'info'", comment='级别(info/success/warning/danger)')
    category = Column(String(32), nullable=False, server_default="'system'", comment='分类(system/trade/backtest/risk)')
    is_read = Column(CHAR(1), nullable=False, server_default='0', comment='是否已读（0否 1是）')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class PlatBacktestRun(Base):
    """
    量化回测运行记录表
    """

    __tablename__ = 'plat_backtest_run'
    __table_args__ = {'comment': '量化回测运行记录表'}

    run_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='回测ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    days = Column(Integer, nullable=False, server_default='120', comment='回测天数')
    strategy = Column(String(64), nullable=False, server_default="'MA5/MA20 cross'", comment='策略名称')
    trades = Column(Integer, nullable=False, server_default='0', comment='交易次数')
    return_pct = Column(Float, nullable=False, server_default='0', comment='收益率(%)')
    final_equity = Column(Float, nullable=False, server_default='0', comment='最终净值')
    max_drawdown = Column(Float, nullable=True, server_default='0', comment='最大回撤(%)')
    win_rate = Column(Float, nullable=True, server_default='0', comment='胜率(%)')
    equity_curve_json = Column(Text, nullable=True, comment='净值曲线JSON')
    message = Column(String(255), nullable=True, comment='执行结果描述')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='执行时间')


class PlatAiBatchRun(Base):
    """
    批量 AI 研判任务记录表
    """

    __tablename__ = 'plat_ai_batch_run'
    __table_args__ = {'comment': '批量 AI 研判任务记录表'}

    batch_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='批次ID')
    cycle_id = Column(String(64), nullable=False, index=True, comment='批次唯一标识')
    symbols_count = Column(Integer, nullable=False, server_default='0', comment='总标的数')
    success_count = Column(Integer, nullable=False, server_default='0', comment='成功数')
    status = Column(CHAR(1), nullable=False, server_default='0', comment='状态(0进行中 1已完成 2失败)')
    summary = Column(Text, nullable=True, comment='批次摘要')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class PlatAiBatchItem(Base):
    """
    批量 AI 研判任务明细表
    """

    __tablename__ = 'plat_ai_batch_item'
    __table_args__ = {'comment': '批量 AI 研判任务明细表'}

    item_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='明细ID')
    batch_id = Column(BigInteger, nullable=False, index=True, comment='所属批次ID')
    symbol = Column(String(32), nullable=False, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    decision = Column(String(32), nullable=True, comment='决策建议')
    confidence = Column(Integer, nullable=True, comment='置信度')
    summary = Column(Text, nullable=True, comment='研判内容')
    status = Column(CHAR(1), nullable=False, server_default='0', comment='状态(0分析中 1成功 2失败)')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class PlatAutoTradeDecision(Base):
    """
    自动交易决策与委托意图表
    """

    __tablename__ = 'plat_auto_trade_decision'
    __table_args__ = {'comment': '自动交易决策与委托意图表'}

    decision_id = Column(
        BigInteger().with_variant(Integer, 'sqlite'),
        primary_key=True,
        autoincrement=True,
        comment='决策ID',
    )
    cycle_id = Column(String(64), nullable=False, index=True, comment='扫描周期ID')
    user_id = Column(BigInteger, nullable=False, server_default='1', index=True, comment='所属用户ID')
    account_id = Column(String(64), nullable=True, comment='账户ID')
    symbol = Column(String(32), nullable=False, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    side = Column(String(10), nullable=False, comment='买卖方向(BUY/SELL)')
    quantity = Column(Integer, nullable=False, comment='委托数量')
    price = Column(Numeric(12, 4), nullable=True, comment='下单参考价')
    confidence = Column(Integer, nullable=True, comment='置信度')
    status = Column(String(32), nullable=False, server_default="'pending'", comment='执行状态(submitted/rejected/skipped/filled)')
    reason = Column(Text, nullable=True, comment='决策依据')
    source = Column(String(32), nullable=False, server_default="'auto'", comment='触发源(auto/scheduler/manual)')
    order_id = Column(String(64), nullable=True, comment='券商真实委托单号')
    error = Column(Text, nullable=True, comment='异常或拒绝原因')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class PlatAiTradeRunLog(Base):
    """
    自选股 AI 自动交易扫描台账
    """

    __tablename__ = 'plat_ai_trade_run_log'
    __table_args__ = {'comment': '自选股 AI 自动交易扫描台账'}

    run_id = Column(
        BigInteger().with_variant(Integer, 'sqlite'),
        primary_key=True,
        autoincrement=True,
        comment='运行记录ID',
    )
    cycle_id = Column(String(64), nullable=False, unique=True, index=True, comment='周期唯一标识')
    user_id = Column(BigInteger, nullable=False, server_default='1', index=True, comment='触发用户ID')
    source = Column(String(32), nullable=False, server_default="'scheduler'", comment='触发来源(scheduler/manual/api)')
    strategy_profile = Column(String(32), nullable=False, server_default="'balanced'", comment='策略档位')
    target_count = Column(Integer, nullable=False, server_default='0', comment='扫描标的数')
    evaluated_count = Column(Integer, nullable=False, server_default='0', comment='已评估标的数')
    opportunity_count = Column(Integer, nullable=False, server_default='0', comment='发现机会数')
    submitted_orders_count = Column(Integer, nullable=False, server_default='0', comment='实际提交订单数')
    status = Column(String(32), nullable=False, server_default="'completed'", comment='运行状态(running/completed/skipped/failed)')
    guardrail_snapshot = Column(Text, nullable=True, comment='日内护栏快照JSON')
    candidates_snapshot = Column(Text, nullable=True, comment='候选与评分快照JSON')
    opportunities_snapshot = Column(Text, nullable=True, comment='机会标的快照JSON')
    skipped_reasons = Column(Text, nullable=True, comment='跳过原因明细JSON')
    message = Column(Text, nullable=True, comment='运行简述')
    started_at = Column(DateTime, nullable=True, default=datetime.now, comment='启动时间')
    finished_at = Column(DateTime, nullable=True, default=datetime.now, comment='结束时间')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='记录时间')
