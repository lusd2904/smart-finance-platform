"""腾讯行情 qt.gtimg.cn 批量抓取（指数与个股共用）。"""

from __future__ import annotations

import re
from typing import Any

from utils.http_fetch import fetch

_UA = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn',
}

# 腾讯行情字段：3=现价 4=昨收 30=时间戳 32=涨跌幅
_IDX_LAST, _IDX_PREV, _IDX_TIME, _IDX_CHGPCT = 3, 4, 30, 32
_MIN_PARTS = 33
_CODE_RE = re.compile(r'v_(\w+)="([^"]*)"')


def to_float(value: Any) -> float | None:
    if value is None or value in {'', '-'}:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def parse_gtimg_text(text: str) -> dict[str, dict[str, Any]]:
    """解析 qt.gtimg.cn 文本，键为不带 v_ 的代码（usAAPL / hk00700 / sh600519）。"""
    quotes: dict[str, dict[str, Any]] = {}
    for match in _CODE_RE.finditer(text or ''):
        parts = match.group(2).split('~')
        if len(parts) < _MIN_PARTS:
            continue
        quotes[match.group(1)] = {
            'name': parts[1],
            'last': to_float(parts[_IDX_LAST]),
            'prevClose': to_float(parts[_IDX_PREV]),
            'quoteTime': parts[_IDX_TIME],
            'changePct': to_float(parts[_IDX_CHGPCT]),
        }
    return quotes


def fetch_tencent_batch(codes: list[str], *, timeout_s: float = 8) -> dict[str, dict[str, Any]]:
    """一次请求多个代码；空列表返回空 dict。"""
    cleaned = [str(code).strip() for code in codes if str(code).strip()]
    if not cleaned:
        return {}
    url = f'https://qt.gtimg.cn/q={",".join(cleaned)}'
    text = fetch(url, timeout_s=timeout_s, headers=_UA, encoding='gbk', retries=1)
    return parse_gtimg_text(text)
