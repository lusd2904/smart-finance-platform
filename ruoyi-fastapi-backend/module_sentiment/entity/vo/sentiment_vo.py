from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel

from utils.time_format_util import format_beijing_datetime

X_MONITOR_INGEST_BATCH_MAX = 200


class SentimentNewsModel(BaseModel):
    """
    舆情资讯表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    news_id: int | None = Field(default=None, description='资讯ID')
    source: str | None = Field(default=None, description='来源')
    title: str | None = Field(default=None, description='标题')
    content: str | None = Field(default=None, description='摘要/正文')
    url: str | None = Field(default=None, description='原文链接')
    pub_time: datetime | None = Field(default=None, description='发布时间')
    uniq_hash: str | None = Field(default=None, description='去重hash')
    analyzed: str | None = Field(default=None, description='是否已分析（0否 1是）')
    create_time: datetime | None = Field(default=None, description='采集时间')

    @field_serializer('pub_time', 'create_time')
    def _serialize_news_times(self, value: datetime | None) -> str | None:
        return format_beijing_datetime(value)


class SentimentNewsPageQueryModel(BaseModel):
    """
    舆情资讯分页查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    source: str | None = Field(default=None, description='来源')
    title: str | None = Field(default=None, description='标题')
    analyzed: str | None = Field(default=None, description='是否已分析')
    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class SentimentAnalysisModel(BaseModel):
    """
    舆情AI分析结果表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    analysis_id: int | None = Field(default=None, description='分析ID')
    news_count: int | None = Field(default=None, description='本次分析的资讯条数')
    news_ids: str | None = Field(default=None, description='本次分析的资讯ID列表')
    summary: str | None = Field(default=None, description='舆情综述')
    us_direction: str | None = Field(default=None, description='美股影响方向')
    us_score: float | None = Field(default=None, description='美股影响分')
    us_reason: str | None = Field(default=None, description='美股影响理由')
    hk_direction: str | None = Field(default=None, description='港股影响方向')
    hk_score: float | None = Field(default=None, description='港股影响分')
    hk_reason: str | None = Field(default=None, description='港股影响理由')
    a_direction: str | None = Field(default=None, description='A股影响方向')
    a_score: float | None = Field(default=None, description='A股影响分')
    a_reason: str | None = Field(default=None, description='A股影响理由')
    risk_events: str | None = Field(default=None, description='风险事件提示')
    model_name: str | None = Field(default=None, description='使用的模型')
    raw_response: str | None = Field(default=None, description='模型原始返回')
    status: str | None = Field(default=None, description='状态（0成功 1失败）')
    error_msg: str | None = Field(default=None, description='失败原因')
    create_time: datetime | None = Field(default=None, description='分析时间')

    @field_serializer('create_time')
    def _serialize_analysis_time(self, value: datetime | None) -> str | None:
        return format_beijing_datetime(value)


class SentimentAnalysisPageQueryModel(BaseModel):
    """
    舆情AI分析结果分页查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    status: str | None = Field(default=None, description='状态')
    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class SentimentAiConfigModel(BaseModel):
    """
    舆情AI配置表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    config_id: int | None = Field(default=None, description='配置ID')
    base_url: str | None = Field(default=None, description='AI接口Base URL（只读，来自AI模型管理）')
    api_key: str | None = Field(default=None, description='AI接口API Key（只读）')
    model_name: str | None = Field(default=None, description='模型名称（只读，来自AI模型管理）')
    temperature: float | None = Field(default=None, description='温度（只读）')
    max_news_per_round: int | None = Field(default=None, description='单次分析最大资讯条数')
    auto_analyze: str | None = Field(default=None, description='采集后自动分析（0否 1是）')
    enabled_sources: str | None = Field(default=None, description='启用的数据源')
    update_by: str | None = Field(default=None, description='更新者')
    update_time: datetime | None = Field(default=None, description='更新时间')

    @field_serializer('update_time')
    def _serialize_config_time(self, value: datetime | None) -> str | None:
        return format_beijing_datetime(value)
    model_scope: str | None = Field(default=None, description='当前复用的模型 scope（只读）')
    model_id: int | None = Field(default=None, description='当前复用的模型ID（只读）')


class DeleteSentimentNewsModel(BaseModel):
    """
    删除舆情资讯模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    news_ids: str = Field(description='需要删除的资讯ID')


class XMonitorIngestItemModel(BaseModel):
    """
    X监测器单条入库条目（客户端 source 会被服务端覆盖为 x_monitor）
    """

    model_config = ConfigDict(extra='ignore', populate_by_name=True)

    posted_at: Any = Field(default=None, description='发布时间')
    author: str | None = Field(default=None, description='作者')
    author_id: str | int | None = Field(default=None, description='作者ID')
    text: str | None = Field(default=None, description='正文')
    url: str | None = Field(default=None, description='原文链接')
    topics: Any = Field(default=None, description='主题，数组或逗号分隔字符串')
    source: str | None = Field(default=None, description='客户端来源，忽略并强制 x_monitor')


class XMonitorIngestRequest(BaseModel):
    """
    X监测器批量入库请求
    """

    items: list[XMonitorIngestItemModel] = Field(
        default_factory=list,
        max_length=X_MONITOR_INGEST_BATCH_MAX,
        description=f'条目列表，最多 {X_MONITOR_INGEST_BATCH_MAX} 条',
    )


class XMonitorIngestResult(BaseModel):
    """
    X监测器批量入库结果
    """

    accepted: int = Field(description='可映射条目数')
    inserted: int = Field(description='新入库条数')
    skipped: int = Field(description='已存在而跳过的条数（按 uniq_hash / url）')
