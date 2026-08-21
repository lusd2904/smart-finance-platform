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
