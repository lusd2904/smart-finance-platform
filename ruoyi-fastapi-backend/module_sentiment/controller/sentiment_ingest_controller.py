"""Token-authenticated X监测器批量入库，无 JWT / PreAuth。"""

import hmac
import os
from typing import Annotated

from fastapi import Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.annotation.rate_limit_annotation import ApiRateLimit
from common.aspect.db_seesion import DBSessionDependency
from common.router import APIRouterPro
from module_sentiment.entity.vo.sentiment_vo import XMonitorIngestRequest
from module_sentiment.service.sentiment_service import SentimentService
from utils.response_util import ResponseUtil

X_MONITOR_INGEST_TOKEN_ENV = 'SFP_X_MONITOR_INGEST_TOKEN'

sentiment_ingest_controller = APIRouterPro(
    prefix='/sentiment/ingest',
    order_num=32,
    tags=['对外-舆情入库'],
)


def _configured_ingest_token() -> str:
    return (os.environ.get(X_MONITOR_INGEST_TOKEN_ENV) or '').strip()


def _tokens_equal(provided: str, expected: str) -> bool:
    left = provided.encode('utf-8')
    right = expected.encode('utf-8')
    if len(left) != len(right):
        hmac.compare_digest(right, right)
        return False
    return hmac.compare_digest(left, right)


def verify_x_monitor_ingest_token(token: str | None) -> None:
    """
    校验 X-Ingest-Token。未配置或错误为 403，缺失为 401。
    """
    expected = _configured_ingest_token()
    provided = (token or '').strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='ingest token is not configured')
    if not provided:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='missing ingest token')
    if not _tokens_equal(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='invalid ingest token')


@sentiment_ingest_controller.post(
    '/x_monitor',
    summary='X监测器批量入库',
    description='Header: X-Ingest-Token。按 url/uniq_hash 幂等写入 sentiment_news，source 强制 x_monitor。',
)
@ApiRateLimit(
    namespace='sentiment:ingest:x_monitor',
    limit=30,
    window_seconds=60,
    algorithm='sliding_window',
    fail_strategy='local_fallback',
)
async def ingest_x_monitor_posts(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    body: XMonitorIngestRequest,
    x_ingest_token: Annotated[str | None, Header(alias='X-Ingest-Token')] = None,
) -> Response:
    verify_x_monitor_ingest_token(x_ingest_token)
    items = [item.model_dump() for item in body.items]
    data = await SentimentService.ingest_x_monitor_services(query_db, items)
    return ResponseUtil.success(data=data)
