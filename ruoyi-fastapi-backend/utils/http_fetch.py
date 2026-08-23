"""统一 HTTP 抓取工具。

基于 urllib 标准库（不引入新依赖），供行情/列表类服务复用：
- 内置默认 User-Agent，可被 headers 覆盖；
- timeout 同时约束连接与读取；
- 重试若干次后仍失败抛 HttpFetchError（非 2xx 同样视为失败）；
- 多编码逐个尝试解码，最终兜底 utf-8/replace。
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils.log_util import logger

DEFAULT_TIMEOUT_S = 10
DEFAULT_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
RETRY_SLEEP_S = 0.4
FALLBACK_ENCODINGS = ('utf-8', 'gbk', 'gb2312')


class HttpFetchError(RuntimeError):
    """HTTP 抓取失败：网络错误、非 2xx 响应或重试耗尽。"""


def _decode(raw: bytes, encoding: str) -> str:
    for enc in (encoding, *FALLBACK_ENCODINGS):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:  # noqa: PERF203 - 多编码逐个尝试
            continue
    return raw.decode('utf-8', 'replace')


def fetch(
    url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    headers: dict[str, str] | None = None,
    encoding: str = 'utf-8',
    retries: int = 3,
) -> str:
    """GET 抓取文本；默认 UA 可被覆盖，重试耗尽或非 2xx 抛 HttpFetchError。"""
    merged = {'User-Agent': DEFAULT_UA}
    if headers:
        merged.update(headers)
    last_err: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            req = Request(url, headers=merged)
            with urlopen(req, timeout=timeout_s) as resp:
                if not 200 <= resp.status < 300:  # noqa: PLR2004 - 2xx 区间判断
                    raise HttpFetchError(f'GET {url} unexpected status {resp.status}')
                raw = resp.read()
            return _decode(raw, encoding)
        except HTTPError as exc:
            last_err = exc
            logger.warning(f'[http_fetch] GET fail attempt={attempt + 1} status={exc.code} url={url[:120]}')
        except (URLError, OSError, HttpFetchError) as exc:
            last_err = exc
            logger.warning(f'[http_fetch] GET fail attempt={attempt + 1} url={url[:120]} err={exc}')
        time.sleep(RETRY_SLEEP_S)
    raise HttpFetchError(f'GET failed {url}: {last_err}') from last_err


def fetch_json(url: str, **kwargs: Any) -> Any:
    """fetch 的 JSON 快捷方式。"""
    return json.loads(fetch(url, **kwargs))


def extract_jsonp(raw: str) -> Any:
    """从 JSONP 文本中提取首个括号包裹的 JSON 并解析。"""
    start = raw.find('(')
    end = raw.rfind(')')
    if start < 0 or end <= start:
        raise ValueError('jsonp payload missing')
    return json.loads(raw[start + 1 : end])
