"""长桥区域归一化与接入端点。"""

from __future__ import annotations


def resolve_region(region: str | None) -> str:
    """归一化区域，默认 cn。"""
    return (str(region or '').strip().lower()) or 'cn'


def endpoints(region: str) -> dict[str, str]:
    """按区域返回长桥接入端点。cn 走 .cn 域名，其余走国际域名。"""
    if region == 'cn':
        return {
            'http_url': 'https://openapi.longbridge.cn',
            'quote_ws_url': 'wss://openapi-quote.longbridge.cn/v2',
            'trade_ws_url': 'wss://openapi-trade.longbridge.cn/v2',
        }
    return {
        'http_url': 'https://openapi.longbridge.com',
        'quote_ws_url': 'wss://openapi-quote.longbridge.com/v2',
        'trade_ws_url': 'wss://openapi-trade.longbridge.com/v2',
    }
