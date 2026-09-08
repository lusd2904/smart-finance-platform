"""
Internal job execution endpoint for Go market-worker delegation.

Heat / briefings / content-cache jobs still run in Python until ported.
Protected by INTERNAL_JOB_TOKEN (X-Internal-Token header).
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from utils.job_queue import HANDLERS, KNOWN_JOBS

router = APIRouter(prefix='/internal/jobs', tags=['internal-jobs'])

_DELEGATABLE = frozenset(
    {
        # market queue — Longbridge SDK only in Python today
        'market_heat_collect',
        'symbol_content',
        # quant queue — heavy factor/strategy logic still Python
        'factor_scan',
        'factor_qc',
        'strategy_run',
        'position_monitor',
        'daily_list_scan',
        'daily_list_open',
        'auto_trade_scan',
        # llm queue — Grok / LLM pipelines
        'sentiment_collect',
        'sentiment_analyze',
        'watchlist_analyze',
        'daily_review',
        'req_send',
        'req_summarize',
        'stock_pick_run',
        'market_review',
        'ai_analyze',
        'ai_batch',
        'user_notice',
    }
)


class InternalJobRequest(BaseModel):
    type: str = Field(..., description='Job type from Redis queue')
    payload: dict[str, Any] = Field(default_factory=dict)


def _expected_token() -> str:
    return str(os.environ.get('INTERNAL_JOB_TOKEN') or '').strip()


@router.post('/run', summary='Execute one delegated market job')
async def run_internal_job(
    body: InternalJobRequest,
    x_internal_token: Annotated[str | None, Header(alias='X-Internal-Token')] = None,
) -> dict[str, Any]:
    token = _expected_token()
    if not token:
        raise HTTPException(status_code=503, detail='INTERNAL_JOB_TOKEN not configured')
    if (x_internal_token or '').strip() != token:
        raise HTTPException(status_code=401, detail='invalid internal token')

    job_type = str(body.type or '').strip()
    if job_type not in KNOWN_JOBS:
        raise HTTPException(status_code=400, detail=f'unknown job type: {job_type}')
    if job_type not in _DELEGATABLE:
        raise HTTPException(status_code=400, detail=f'job type not delegatable: {job_type}')

    handler = HANDLERS.get(job_type)
    if handler is None:
        raise HTTPException(status_code=400, detail=f'no handler: {job_type}')

    result = await handler(body.payload or {})
    return {'ok': True, 'type': job_type, 'result': result}
