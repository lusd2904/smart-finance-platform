from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Float, Integer, String, Text

from config.database import Base
from config.env import DataBaseConfig
from utils.common_util import SqlalchemyUtil


class SentimentNews(Base):
    """
    舆情资讯表
    """

    __tablename__ = 'sentiment_news'
    __table_args__ = {'comment': '舆情资讯表'}

    news_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='资讯ID')
    source = Column(String(50), nullable=False, comment='来源（eastmoney/sina等）')
    title = Column(String(500), nullable=False, comment='标题')
    content = Column(Text, nullable=True, comment='摘要/正文')
    url = Column(String(1000), nullable=True, comment='原文链接')
    pub_time = Column(DateTime, nullable=True, comment='发布时间')
    uniq_hash = Column(String(64), nullable=False, unique=True, index=True, comment='去重hash')
    analyzed = Column(CHAR(1), nullable=False, server_default='0', comment='是否已分析（0否 1是）')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='采集时间')


class SentimentAnalysis(Base):
    """
    舆情AI分析结果表
    """

    __tablename__ = 'sentiment_analysis'
    __table_args__ = {'comment': '舆情AI分析结果表'}

    analysis_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='分析ID')
    news_count = Column(Integer, nullable=False, server_default='0', comment='本次分析的资讯条数')
    news_ids = Column(Text, nullable=True, comment='本次分析的资讯ID列表（逗号分隔）')
    summary = Column(Text, nullable=True, comment='舆情综述')
    us_direction = Column(String(10), nullable=True, comment='美股三大指数影响方向（利多/利空/中性）')
    us_score = Column(Float, nullable=True, comment='美股影响分（-10~10）')
    us_reason = Column(Text, nullable=True, comment='美股影响理由')
    hk_direction = Column(String(10), nullable=True, comment='港股指数影响方向')
    hk_score = Column(Float, nullable=True, comment='港股影响分（-10~10）')
    hk_reason = Column(Text, nullable=True, comment='港股影响理由')
    a_direction = Column(String(10), nullable=True, comment='A股指数影响方向')
    a_score = Column(Float, nullable=True, comment='A股影响分（-10~10）')
    a_reason = Column(Text, nullable=True, comment='A股影响理由')
    risk_events = Column(Text, nullable=True, comment='风险事件提示')
    model_name = Column(String(100), nullable=True, comment='使用的模型')
    raw_response = Column(Text, nullable=True, comment='模型原始返回')
    status = Column(CHAR(1), nullable=False, server_default='0', comment='状态（0成功 1失败）')
    error_msg = Column(
        String(2000),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='失败原因',
    )
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='分析时间')


class SentimentAiConfig(Base):
    """
    舆情AI配置表
    """

    __tablename__ = 'sentiment_ai_config'
    __table_args__ = {'comment': '舆情AI配置表'}

    config_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='配置ID')
    base_url = Column(String(255), nullable=True, comment='AI接口Base URL')
    api_key = Column(String(255), nullable=True, comment='AI接口API Key')
    model_name = Column(String(100), nullable=True, comment='模型名称')
    temperature = Column(Float, nullable=True, server_default='0.2', comment='温度')
    max_news_per_round = Column(Integer, nullable=True, server_default='200', comment='单次分析最大资讯条数')
    auto_analyze = Column(CHAR(1), nullable=False, server_default='1', comment='采集后自动分析（0否 1是）')
    enabled_sources = Column(
        String(255), nullable=True, server_default="'eastmoney,sina,ths,wallstreetcn,google_news,x_monitor'", comment='启用的数据源（逗号分隔）'
    )
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now, comment='更新时间')
