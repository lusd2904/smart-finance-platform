"""Anonymous encrypted sync login and JWT-scoped data pull."""

from typing import Annotated, Any

from fastapi import Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.constant import ApiNamespace
from common.router import APIRouterPro
from module_admin.service.open_sync_service import OpenSyncService
from utils.response_util import ResponseUtil

open_sync_controller = APIRouterPro(prefix='/open/sync', order_num=90, tags=['对外-数据同步'])


class OpenSyncTokenRequest(BaseModel):
    username: str = Field(min_length=1, description='用户名')
    password: str = Field(min_length=1, description='密码')


class OpenSyncPullRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    datasets: list[str] = Field(min_length=1, description='数据集列表')
    markets: list[str] | None = Field(default=None, description='市场 US/CN/HK')
    since: str | None = Field(default=None, description='起始日期 YYYY-MM-DD')
    cursor: Any = Field(default=None, description='分页游标')
    limit: int | None = Field(default=None, description='每页行数')


@open_sync_controller.post(
    '/token',
    summary='数据同步登录',
    description='加密传输用户名密码，签发 scope=sync 的短时 JWT。不接受静态 Token。',
)
@ApiRateLimit(namespace=ApiNamespace.LOGIN, preset=ApiRateLimitPreset.ANON_AUTH_LOGIN)
async def open_sync_token(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: OpenSyncTokenRequest,
) -> Response:
    data = await OpenSyncService.issue_token(request, query_db, body.username, body.password)
    return ResponseUtil.success(data=data)


@open_sync_controller.post(
    '/pull',
    summary='数据同步拉取',
    description='Bearer JWT（scope=sync）分页拉取白名单表/日K，禁止导出密钥与用户密码。',
)
@ApiRateLimit(
    namespace='open:sync:pull',
    limit=90,
    window_seconds=60,
    algorithm='sliding_window',
    fail_strategy='local_fallback',
)
async def open_sync_pull(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: OpenSyncPullRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    await OpenSyncService.verify_pull_token(request, authorization)
    data = await OpenSyncService.pull(
        query_db,
        datasets=body.datasets,
        markets=body.markets,
        since=body.since,
        cursor=body.cursor,
        limit=body.limit,
    )
    return ResponseUtil.success(data=data)
