from __future__ import annotations

import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from utils.log_util import logger

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    HTTP_REQUESTS = Counter(
        'http_requests_total',
        'Total HTTP requests',
        ['method', 'path', 'status'],
    )
    HTTP_LATENCY = Histogram(
        'http_request_duration_seconds',
        'HTTP request latency in seconds',
        ['method', 'path'],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    PROMETHEUS_AVAILABLE = True
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
    HTTP_REQUESTS = None
    HTTP_LATENCY = None
    PROMETHEUS_AVAILABLE = False


def _path_label(path: str) -> str:
    parts = [p for p in path.split('/') if p][:3]
    return '/' + '/'.join(parts) if parts else '/'


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == '/metrics' or not PROMETHEUS_AVAILABLE:
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        path = _path_label(request.url.path)
        try:
            HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
            HTTP_LATENCY.labels(request.method, path).observe(elapsed)
        except Exception as exc:
            logger.debug(f'[metrics] record failed: {exc}')
        return response


def add_metrics_middleware(app: FastAPI) -> None:
    app.add_middleware(MetricsMiddleware)


def render_metrics() -> Response:
    if not PROMETHEUS_AVAILABLE:
        return Response('# prometheus_client not installed\n', media_type='text/plain')
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
