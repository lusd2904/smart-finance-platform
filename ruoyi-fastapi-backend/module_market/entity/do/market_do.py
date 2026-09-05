from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from config.database import Base


class MarketInstrument(Base):
    """
    行情标的元数据表
    """

    __tablename__ = 'market_instrument'
    __table_args__ = {'comment': '行情标的元数据表'}

    instrument_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='标的ID')
    symbol = Column(String(32), nullable=False, unique=True, index=True, comment='标准符号（如AAPL/^DJI）')
    name = Column(String(100), nullable=True, comment='名称')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场（US/CN/HK）')
    category = Column(
        String(20),
        nullable=False,
        server_default="'star'",
        comment='分类（index/mag7/star/semiconductor/software）',
    )
    enabled = Column(CHAR(1), nullable=False, server_default='1', comment='是否启用（0否 1是）')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class MarketPriceHistoryDaily(Base):
    """
    日K 历史行情表（MySQL 权威落库，再同步到 Influx 时序库）
    """

    __tablename__ = 'market_price_history_daily'
    __table_args__ = (
        UniqueConstraint('symbol', 'trade_date', name='uniq_symbol_trade_date'),
        {'comment': '日K历史行情表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    trade_date = Column(String(10), nullable=False, index=True, comment='交易日 YYYY-MM-DD')
    open_price = Column(Float, nullable=True, comment='开盘价')
    high_price = Column(Float, nullable=True, comment='最高价')
    low_price = Column(Float, nullable=True, comment='最低价')
    close_price = Column(Float, nullable=True, comment='收盘价')
    volume = Column(Float, nullable=True, comment='成交量')
    turnover = Column(Float, nullable=True, comment='成交额')
    source = Column(String(32), nullable=True, server_default="'sina'", comment='数据来源')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class SymbolAiAnalysis(Base):
    """
    标的 AI 研判历史表（单次 LLM 调用结果落库）
    """

    __tablename__ = 'symbol_ai_analysis'
    __table_args__ = {'comment': '标的AI研判历史表'}

    analysis_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='分析ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场（US/CN/HK）')
    price = Column(Float, nullable=True, comment='分析时价格')
    final_decision = Column(String(16), nullable=True, comment='最终结论（买/卖/观望 或 BUY/SELL/HOLD）')
    final_confidence = Column(Integer, nullable=True, comment='置信度 0-100')
    summary_text = Column(Text, nullable=True, comment='分析摘要')
    indicators_json = Column(Text, nullable=True, comment='指标快照JSON')
    raw_json = Column(Text, nullable=True, comment='模型原始结构化JSON')
    model_name = Column(String(100), nullable=True, comment='使用的模型')
    analysis_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='分析时间')


class FinanceBriefing(Base):
    """
    财经资讯/市场简报表
    """

    __tablename__ = 'finance_briefing'
    __table_args__ = {'comment': '财经资讯简报表'}

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    market = Column(String(10), nullable=False, index=True, comment='市场（US/CN/HK）')
    briefing_type = Column(
        String(32),
        nullable=False,
        server_default="'internal'",
        comment='类型（market-insight/market-ai-scan/market-news/recommendation/internal）',
    )
    headline = Column(String(255), nullable=False, comment='标题')
    summary = Column(Text, nullable=True, comment='摘要')
    source_name = Column(String(80), nullable=True, server_default="'system'", comment='来源名')
    source_link = Column(String(2048), nullable=True, comment='原文链接')
    payload_json = Column(Text, nullable=True, comment='扩展载荷JSON')
    generated_at = Column(DateTime, nullable=False, default=datetime.now, index=True, comment='生成时间')
    expires_at = Column(DateTime, nullable=True, index=True, comment='过期时间')


class SymbolContentCache(Base):
    """
    标的公告/资讯/讨论内容缓存表
    """

    __tablename__ = 'symbol_content_cache'
    __table_args__ = (
        UniqueConstraint('symbol', 'content_type', 'source_name', 'source_item_id', name='uniq_symbol_content'),
        {'comment': '标的公告资讯讨论缓存表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, comment='市场')
    content_type = Column(String(24), nullable=False, index=True, comment='announcement/news/topic')
    source_name = Column(String(64), nullable=False, server_default="'longbridge'", comment='来源名')
    source_item_id = Column(String(128), nullable=True, comment='来源侧条目ID')
    title = Column(String(255), nullable=False, comment='标题')
    summary = Column(Text, nullable=True, comment='摘要')
    source_link = Column(String(1000), nullable=True, comment='原文链接')
    published_at = Column(DateTime, nullable=True, comment='发布时间')
    fetched_at = Column(DateTime, nullable=False, default=datetime.now, comment='拉取时间')
    expires_at = Column(DateTime, nullable=True, index=True, comment='过期时间')
    payload_json = Column(Text, nullable=True, comment='原始载荷JSON')


class MarketWatchlist(Base):
    """
    行情中心自选清单（关注标的，供小时级 AI 综合分析）
    """

    __tablename__ = 'market_watchlist'
    __table_args__ = (
        UniqueConstraint('user_id', 'symbol', 'market', name='uk_market_watchlist_user_symbol'),
        {'comment': '行情中心自选清单'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    user_id = Column(BigInteger, nullable=False, server_default='1', index=True, comment='用户ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场 US/HK/CN')
    name = Column(String(100), nullable=True, comment='名称')
    note = Column(String(255), nullable=True, comment='备注')
    groups = Column('groups', String(255), nullable=True, comment='分组，逗号分隔')
    enabled = Column(CHAR(1), nullable=False, server_default='1', comment='是否启用（0否 1是）')
    sort_order = Column(Integer, nullable=False, server_default='0', comment='排序')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='加入时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class MarketWatchlistAnalysis(Base):
    """
    自选清单小时级 AI 综合分析记录
    """

    __tablename__ = 'market_watchlist_analysis'
    __table_args__ = {'comment': '行情自选综合分析'}

    analysis_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='分析ID')
    watchlist_id = Column(BigInteger, nullable=True, index=True, comment='自选ID')
    user_id = Column(BigInteger, nullable=True, server_default='1', index=True, comment='用户ID')
    symbol = Column(String(32), nullable=False, index=True, comment='标的代码')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    price = Column(Float, nullable=True, comment='分析时价格')
    change_percent = Column(Float, nullable=True, comment='涨跌幅百分比')
    stance = Column(String(16), nullable=True, comment='立场 偏多/偏空/中性')
    recommendation = Column(String(16), nullable=True, comment='建议 买入/加仓/持有/观望/减仓/卖出')
    confidence = Column(Integer, nullable=True, comment='置信度 0-100')
    summary = Column(Text, nullable=True, comment='综合摘要')
    indicator_review = Column(Text, nullable=True, comment='指标解读')
    news_review = Column(Text, nullable=True, comment='长桥资讯解读')
    sentiment_review = Column(Text, nullable=True, comment='舆情解读')
    operation_advice = Column(Text, nullable=True, comment='操作建议')
    risk_warning = Column(Text, nullable=True, comment='风险提示')
    source = Column(String(16), nullable=True, server_default="'ai'", comment='来源 ai/rule')
    model_name = Column(String(100), nullable=True, comment='模型名')
    indicators_json = Column(Text, nullable=True, comment='指标快照 JSON')
    news_json = Column(Text, nullable=True, comment='资讯摘要 JSON')
    sentiment_json = Column(Text, nullable=True, comment='舆情摘要 JSON')
    raw_json = Column(Text, nullable=True, comment='模型原始 JSON')
    analysis_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='分析时间')


class MarketHeatDaily(Base):
    """分市场每日热度快照。"""

    __tablename__ = 'market_heat_daily'
    __table_args__ = (
        UniqueConstraint('market', 'trade_date', name='uk_market_heat_daily'),
        {'comment': '分市场每日热度快照'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    market = Column(String(10), nullable=False, index=True, comment='市场 US/HK/CN')
    trade_date = Column(String(10), nullable=False, index=True, comment='交易日 YYYY-MM-DD')
    index_symbol = Column(String(32), nullable=True, comment='基准指数代码')
    index_name = Column(String(100), nullable=True, comment='基准指数名称')
    index_change_pct = Column(Float, nullable=True, comment='指数涨跌幅%')
    total_turnover = Column(Float, nullable=True, comment='样本成交额合计')
    advance_count = Column(Integer, nullable=True, comment='上涨家数')
    decline_count = Column(Integer, nullable=True, comment='下跌家数')
    flat_count = Column(Integer, nullable=True, comment='平盘家数')
    heat_score = Column(Float, nullable=True, comment='热度分 0-100')
    heat_summary = Column(String(500), nullable=True, comment='热度摘要')
    currency = Column(String(10), nullable=True, comment='成交额货币')
    filter_rule = Column(String(200), nullable=True, comment='Top50 市值过滤规则')
    weights_json = Column(Text, nullable=True, comment='权重 JSON')
    as_of_time = Column(DateTime, nullable=True, comment='数据采集时间')
    status = Column(String(20), nullable=True, server_default="'ok'", comment='状态 ok/stale/empty/error')
    message = Column(String(500), nullable=True, comment='状态说明')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class MarketTop50Snapshot(Base):
    """收盘后成交额 Top50 快照（按市值过滤）。"""

    __tablename__ = 'market_top50_snapshot'
    __table_args__ = (
        UniqueConstraint('market', 'trade_date', 'symbol', name='uk_market_top50_symbol'),
        {'comment': '分市场 Top50 成交额快照'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='主键')
    market = Column(String(10), nullable=False, index=True, comment='市场 US/HK/CN')
    trade_date = Column(String(10), nullable=False, index=True, comment='交易日 YYYY-MM-DD')
    rank_no = Column(Integer, nullable=False, comment='排名 1-50')
    symbol = Column(String(32), nullable=False, comment='标的代码')
    name = Column(String(100), nullable=True, comment='名称')
    market_cap = Column(Float, nullable=True, comment='市值')
    turnover = Column(Float, nullable=True, comment='成交额')
    change_pct = Column(Float, nullable=True, comment='涨跌幅%')
    last = Column(Float, nullable=True, comment='最新价')
    currency = Column(String(10), nullable=True, comment='货币')
    as_of_time = Column(DateTime, nullable=True, comment='快照时间')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class MarketStockPick(Base):
    """全市场智能选股单（按交易日一份）。"""

    __tablename__ = 'market_stock_pick'
    __table_args__ = (
        UniqueConstraint('trade_date', name='uk_market_stock_pick_date'),
        {'comment': '全市场智能选股单'},
    )

    pick_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='选股单ID')
    trade_date = Column(String(10), nullable=False, index=True, comment='交易日 YYYY-MM-DD')
    status = Column(String(16), nullable=False, server_default="'ok'", comment='running/ok/partial/empty/error')
    trigger_source = Column(String(16), nullable=True, server_default="'manual'", comment='manual/schedule')
    scanned_count = Column(Integer, nullable=True, server_default='0', comment='扫描标的数')
    picked_count = Column(Integer, nullable=True, server_default='0', comment='入选数')
    ai_count = Column(Integer, nullable=True, server_default='0', comment='AI 覆盖数')
    model_name = Column(String(100), nullable=True, comment='模型名')
    open_markets = Column(String(32), nullable=True, comment='当时开盘市场 US,HK,CN')
    context_json = Column(Text, nullable=True, comment='大盘/舆情/热度上下文 JSON')
    message = Column(String(500), nullable=True, comment='状态说明')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')


class MarketStockPickItem(Base):
    """智能选股单标的。"""

    __tablename__ = 'market_stock_pick_item'
    __table_args__ = (
        UniqueConstraint('pick_id', 'symbol', 'market', name='uk_market_stock_pick_item'),
        {'comment': '全市场智能选股条目'},
    )

    item_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='条目ID')
    pick_id = Column(BigInteger, nullable=False, index=True, comment='选股单ID')
    rank_no = Column(Integer, nullable=False, server_default='0', comment='分市场排名')
    symbol = Column(String(32), nullable=False, comment='代码')
    name = Column(String(100), nullable=True, comment='名称')
    market = Column(String(10), nullable=False, server_default="'US'", comment='市场')
    price = Column(Float, nullable=True, comment='最新价')
    change_pct = Column(Float, nullable=True, comment='涨跌幅%')
    factor_score = Column(Float, nullable=True, comment='因子综合分')
    pick_score = Column(Float, nullable=True, comment='选股综合分')
    signal = Column(String(8), nullable=True, comment='BUY/HOLD/SELL')
    recommendation = Column(String(16), nullable=True, comment='买入/关注/观望/回避')
    stance = Column(String(16), nullable=True, comment='偏多/偏空/中性')
    confidence = Column(Integer, nullable=True, comment='置信度')
    summary = Column(Text, nullable=True, comment='综合摘要')
    indicator_review = Column(Text, nullable=True, comment='指标解读')
    sentiment_review = Column(Text, nullable=True, comment='舆情解读')
    operation_advice = Column(Text, nullable=True, comment='操作建议')
    risk_warning = Column(Text, nullable=True, comment='风险提示')
    tags_json = Column(Text, nullable=True, comment='标签 JSON')
    source = Column(String(16), nullable=True, server_default="'rule'", comment='ai/rule')
    factor_json = Column(Text, nullable=True, comment='因子快照 JSON')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')


class MarketDailyReview(Base):
    """三市场收盘复盘（美股 / 港股 / A股），每天每市场一条。"""

    __tablename__ = 'market_daily_review'
    __table_args__ = (
        UniqueConstraint('market', 'trade_date', name='uk_market_daily_review'),
        {'comment': '市场收盘分析日报'},
    )

    review_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='报告ID')
    market = Column(String(10), nullable=False, index=True, comment='市场 US/HK/CN')
    trade_date = Column(String(10), nullable=False, index=True, comment='交易日 YYYY-MM-DD')
    title = Column(String(200), nullable=True, comment='标题')
    stance = Column(String(16), nullable=True, comment='立场 偏多/偏空/中性')
    score = Column(Integer, nullable=True, comment='市场温度 0-100')
    summary = Column(Text, nullable=True, comment='当日复盘摘要')
    index_review = Column(Text, nullable=True, comment='指数与代表股解读')
    news_review = Column(Text, nullable=True, comment='资讯解读')
    sentiment_review = Column(Text, nullable=True, comment='舆情解读')
    outlook = Column(Text, nullable=True, comment='次日关注')
    risk_warning = Column(Text, nullable=True, comment='风险提示')
    source = Column(String(16), nullable=True, server_default="'ai'", comment='来源 ai/rule')
    model_name = Column(String(100), nullable=True, comment='模型名')
    context_json = Column(Text, nullable=True, comment='分析上下文 JSON')
    raw_json = Column(Text, nullable=True, comment='模型原始 JSON')
    analysis_time = Column(DateTime, nullable=True, default=datetime.now, index=True, comment='分析时间')
