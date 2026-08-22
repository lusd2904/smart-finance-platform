"""行情报价公共工具：跨模块共享的报价构造与标的规范化，避免多处复制粘贴演化出逻辑分叉。"""
from __future__ import annotations

from typing import Any


def build_quote_from_klines(klines: list[dict[str, Any]]) -> dict[str, Any]:
    """
    从日K序列构造标准报价结构（取最后一根为最新，倒数第二根为昨收）。

    :param klines: 升序K线列表 [{date, open, high, low, close, volume}, ...]
    :return: 报价 dict，空序列返回 {}
    """
    if not klines:
        return {}
    last = klines[-1]
    prev = klines[-2] if len(klines) > 1 else None
    change = change_rate = None
    try:
        if prev and prev.get('close') and last.get('close'):
            change = round(float(last['close']) - float(prev['close']), 4)
            change_rate = round(change / float(prev['close']) * 100, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return {
        'last': last.get('close'),
        'open': last.get('open'),
        'high': last.get('high'),
        'low': last.get('low'),
        'volume': last.get('volume'),
        'tradeDate': last.get('date'),
        'change': change,
        'changeRate': change_rate,
        'prevClose': prev.get('close') if prev else None,
    }


def normalize_symbol(symbol: str) -> str:
    """标的代码规范化：去空白、转大写、去市场前缀点号后空白。"""
    return str(symbol or '').strip().upper()


def normalize_market(market: str | None, default: str = 'US') -> str:
    """市场规范化：空值回退默认 US。"""
    return (str(market or '').strip().upper() or default)
