from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MarketInstrumentModel(BaseModel):
    """
    行情标的元数据表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    instrument_id: int | None = Field(default=None, description='标的ID')
    symbol: str | None = Field(default=None, description='标准符号')
    name: str | None = Field(default=None, description='名称')
    market: str | None = Field(default=None, description='市场（US/CN/HK）')
    category: str | None = Field(default=None, description='分类')
    enabled: str | None = Field(default=None, description='是否启用（0否 1是）')
    create_time: datetime | None = Field(default=None, description='创建时间')


class MarketInstrumentQueryModel(BaseModel):
    """
    行情标的查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    category: str | None = Field(default=None, description='分类')
    market: str | None = Field(default=None, description='市场')
    enabled: str | None = Field(default=None, description='是否启用')
    keyword: str | None = Field(default=None, description='代码或名称关键字')


class MarketInstrumentUniverseQueryModel(BaseModel):
    """全市场标的分页查询（含 listed，强制分页）"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    market: str | None = Field(default=None, description='市场 US/HK/CN，空=全部')
    keyword: str | None = Field(default=None, description='代码或名称关键字')
    enabled: str | None = Field(default='1', description='是否启用')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=50, description='每页记录数，最大200')


class KlineQueryModel(BaseModel):
    """
    K线查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str = Field(description='标准符号')
    market: str = Field(default='US', description='市场（US/CN/HK）')
    period: str = Field(
        default='daily',
        description='周期：intraday/1min/5min/15min/daily/weekly/monthly（分钟级需时序库或长桥）',
    )
    start: str = Field(default='-2y', description='起始时间（Flux时间或YYYY-MM-DD）')
    stop: str = Field(default='now()', description='结束时间')


class IndicatorQueryModel(BaseModel):
    """
    技术指标查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str = Field(description='标准符号')
    market: str = Field(default='US', description='市场（US/CN/HK）')
    start: str = Field(default='-2y', description='起始时间')
    stop: str = Field(default='now()', description='结束时间')


class MarketSyncModel(BaseModel):
    """
    手动同步请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str | None = Field(default=None, description='指定标的symbol，不传则同步全部目标标的')
    years: int = Field(default=10, description='同步近N年数据')


class MarketAiAnalyzeModel(BaseModel):
    """
    AI行情分析请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str = Field(description='标准符号')
    market: str = Field(default='US', description='市场（US/CN/HK）')
    days: int = Field(default=120, description='喂给模型的近N个交易日K线')


class SymbolOverviewQueryModel(BaseModel):
    """
    标的详情概览查询
    """

    model_config = ConfigDict(alias_generator=to_camel)

    market: str = Field(default='US', description='市场（US/CN/HK）')
    include: str = Field(default='core', description='core=首屏轻量 / all=补全')
    history_limit: int = Field(default=120, description='历史K线条数')


class SymbolContentQueryModel(BaseModel):
    """
    标的内容缓存查询
    """

    model_config = ConfigDict(alias_generator=to_camel)

    market: str = Field(default='US', description='市场')
    content_type: str = Field(default='news', description='announcement|news|topic')
    limit: int = Field(default=20, description='条数上限')
    refresh: bool = Field(default=False, description='是否强制刷新外部源')


class FinanceBriefingQueryModel(BaseModel):
    """
    财经资讯简报查询
    """

    model_config = ConfigDict(alias_generator=to_camel)

    market: str | None = Field(default=None, description='市场 US/CN/HK，空=全部')
    limit: int = Field(default=20, description='条数，最大60')
    refresh: bool = Field(default=False, description='是否强制重新生成后再查询')


class MarketWatchlistModel(BaseModel):
    """行情中心自选清单"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    id: int | None = Field(default=None, description='主键')
    user_id: int | None = Field(default=None, description='用户ID')
    symbol: str | None = Field(default=None, description='标的代码')
    market: str | None = Field(default=None, description='市场')
    name: str | None = Field(default=None, description='名称')
    note: str | None = Field(default=None, description='备注')
    enabled: str | None = Field(default=None, description='是否启用')
    sort_order: int | None = Field(default=None, description='排序')
    create_time: datetime | None = Field(default=None, description='加入时间')


class MarketWatchlistPageQueryModel(BaseModel):
    """自选清单分页查询"""

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str | None = Field(default=None, description='标的代码')
    market: str | None = Field(default=None, description='市场')
    enabled: str | None = Field(default=None, description='是否启用')
    user_id: int | None = Field(default=None, description='用户ID（服务端填充）')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=20, description='每页记录数')


class AddMarketWatchlistModel(BaseModel):
    """新增行情自选"""

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str = Field(description='标的代码')
    market: str = Field(default='US', description='市场 US/HK/CN')
    note: str | None = Field(default=None, description='备注')


class MarketWatchlistAnalyzeModel(BaseModel):
    """触发自选综合分析"""

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str | None = Field(default=None, description='指定标的，空则分析全部启用自选')
    market: str | None = Field(default=None, description='市场')
    refresh_content: bool = Field(default=True, description='分析前是否刷新长桥资讯缓存')
