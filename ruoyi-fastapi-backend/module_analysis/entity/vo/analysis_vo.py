from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AnalysisJobStatusModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    status: str = Field(description='状态（0正常 1暂停）')


class AnalysisRunningJobModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    type: str = Field(description='队列任务类型')
    started_at: str | None = Field(default=None, description='开始时间')
