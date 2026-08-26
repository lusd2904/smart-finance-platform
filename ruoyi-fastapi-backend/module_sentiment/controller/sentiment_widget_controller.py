from typing import Annotated

from fastapi import Header, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.constant import ApiNamespace
from common.router import APIRouterPro
from module_admin.service.open_access_service import OpenAccessService
from module_sentiment.service.sentiment_service import SentimentService
from utils.response_util import ResponseUtil

sentiment_widget_controller = APIRouterPro(
    prefix='/sentiment/widget',
    order_num=31,
    tags=['对外-舆情大盘'],
)

_WIDGET_CORS_HEADERS = {'Access-Control-Allow-Origin': '*'}


class OpenTokenRequest(BaseModel):
    username: str = Field(min_length=1, description='用户名')
    password: str = Field(min_length=1, description='密码')


@sentiment_widget_controller.post(
    '/token',
    summary='舆情 Widget 登录换令牌',
    description='RSA-OAEP+AES-GCM 加密用户名密码，签发 60 分钟 JWT。明文密码拒绝。',
)
@ApiRateLimit(namespace=ApiNamespace.LOGIN, preset=ApiRateLimitPreset.ANON_AUTH_LOGIN)
async def sentiment_widget_token(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: OpenTokenRequest,
) -> Response:
    data = await OpenAccessService.issue_token(request, query_db, body.username, body.password)
    return ResponseUtil.success(data=data, headers=_WIDGET_CORS_HEADERS)


@sentiment_widget_controller.get(
    '/dashboard',
    summary='舆情大盘 Widget 聚合数据',
    description='Header: Authorization: Bearer <token>。先 POST /sentiment/widget/token。',
)
async def sentiment_widget_dashboard(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    trend_limit: Annotated[int, Query(alias='trendLimit', description='趋势点数，默认 24，最大 100')] = 24,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    await OpenAccessService.verify_bearer(request, authorization)
    data = await SentimentService.get_widget_dashboard_services(query_db, trend_limit=trend_limit)
    return ResponseUtil.success(data=data, headers=_WIDGET_CORS_HEADERS)
