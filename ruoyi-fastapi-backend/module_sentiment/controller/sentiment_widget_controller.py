from typing import Annotated

from fastapi import Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.db_seesion import DBSessionDependency
from common.router import APIRouterPro
from config.env import AppConfig
from exceptions.exception import ServiceException
from module_sentiment.service.sentiment_service import SentimentService
from utils.response_util import ResponseUtil

sentiment_widget_controller = APIRouterPro(
    prefix='/sentiment/widget',
    order_num=31,
    tags=['对外-舆情大盘'],
)

_WIDGET_CORS_HEADERS = {'Access-Control-Allow-Origin': '*'}


def _check_widget_token(token: str | None) -> None:
    expected = (AppConfig.sentiment_widget_token or '').strip()
    if not expected:
        raise ServiceException(message='未配置 SENTIMENT_WIDGET_TOKEN，舆情大盘 Widget 接口未开启')
    if (token or '').strip() != expected:
        raise ServiceException(message='Widget 令牌无效')


@sentiment_widget_controller.get(
    '/dashboard',
    summary='舆情大盘 Widget 聚合数据（Token）',
    description='Header: X-Widget-Token。供 macOS Widget / Scriptable 等只读客户端拉取大盘数据。',
)
async def sentiment_widget_dashboard(
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    trend_limit: Annotated[int, Query(alias='trendLimit', description='趋势点数，默认 24，最大 100')] = 24,
    x_widget_token: Annotated[str | None, Header()] = None,
) -> Response:
    _check_widget_token(x_widget_token)
    data = await SentimentService.get_widget_dashboard_services(query_db, trend_limit=trend_limit)
    return ResponseUtil.success(data=data, headers=_WIDGET_CORS_HEADERS)
