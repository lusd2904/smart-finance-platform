from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class QuantWatchlistModel(BaseModel):
    """
    量化自选池表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    id: int | None = Field(default=None, description='主键ID')
    user_id: int | None = Field(default=None, description='所属用户ID')
    symbol: str | None = Field(default=None, description='标的代码')
    market: str | None = Field(default=None, description='市场（US/HK/CN）')
    note: str | None = Field(default=None, description='备注')
    enabled: str | None = Field(default=None, description='是否启用（0否 1是）')
    create_time: datetime | None = Field(default=None, description='加入时间')


class QuantWatchlistPageQueryModel(BaseModel):
    """
    量化自选池分页查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str | None = Field(default=None, description='标的代码')
    market: str | None = Field(default=None, description='市场')
    enabled: str | None = Field(default=None, description='是否启用')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class QuantStrategyRunModel(BaseModel):
    """
    量化策略运行记录表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    run_id: int | None = Field(default=None, description='运行ID')
    cycle_id: str | None = Field(default=None, description='批次ID')
    strategy_profile: str | None = Field(default=None, description='策略档位')
    symbols_count: int | None = Field(default=None, description='参与标的数')
    signal_count: int | None = Field(default=None, description='产出信号数')
    create_time: datetime | None = Field(default=None, description='运行时间')


class QuantStrategyRunPageQueryModel(BaseModel):
    """
    量化策略运行记录分页查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    strategy_profile: str | None = Field(default=None, description='策略档位')
    begin_time: str | None = Field(default=None, description='开始时间')
    end_time: str | None = Field(default=None, description='结束时间')
    page_num: int = Field(default=1, description='当前页码')
    page_size: int = Field(default=10, description='每页记录数')


class QuantStrategySignalModel(BaseModel):
    """
    量化策略信号表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    signal_id: int | None = Field(default=None, description='信号ID')
    run_id: int | None = Field(default=None, description='所属运行ID')
    symbol: str | None = Field(default=None, description='标的代码')
    signal: str | None = Field(default=None, description='信号（BUY/HOLD/SELL）')
    score: float | None = Field(default=None, description='综合打分')
    confidence: int | None = Field(default=None, description='置信度')
    reason: str | None = Field(default=None, description='信号理由')
    factor_json: str | None = Field(default=None, description='因子明细JSON')
    create_time: datetime | None = Field(default=None, description='生成时间')


class QuantLongbridgeConfigModel(BaseModel):
    """
    长桥凭据配置表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    id: int | None = Field(default=None, description='配置ID')
    user_id: int | None = Field(default=None, description='用户ID')
    app_key: str | None = Field(default=None, description='长桥App Key')
    app_secret: str | None = Field(default=None, description='长桥App Secret')
    access_token: str | None = Field(default=None, description='长桥Access Token')
    region: str | None = Field(default=None, description='区域')
    update_time: datetime | None = Field(default=None, description='更新时间')


class AddQuantWatchlistModel(BaseModel):
    """
    新增自选标的模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    symbol: str = Field(description='标的代码')
    market: str = Field(default='US', description='市场（US/HK/CN）')
    note: str | None = Field(default=None, description='备注')


class RunStrategyModel(BaseModel):
    """
    触发策略运行请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel)

    profile: str = Field(default='balanced', description='策略档位（conservative/balanced/aggressive）')
    symbols: list[str] | None = Field(default=None, description='标的列表，不传则使用自选池')
