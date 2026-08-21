"""长桥盘口/成交/K线映射。无 SDK、无日志依赖，便于单测。不补造档位或 K 线。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CN_NO_DEPTH_MSG = 'A股暂无实时盘口'


def is_cn_market(market: str | None, symbol: str | None = None) -> bool:
    mkt = str(market or '').strip().upper()
    if mkt in {'CN', 'SH', 'SZ', 'A'}:
        return True
    raw = str(symbol or '').strip().upper()
    return raw.endswith('.SH') or raw.endswith('.SZ')


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_ts(value: Any, with_time: bool = False) -> str:
    if value is None or value == '':
        return ''
    fmt = '%Y-%m-%d %H:%M:%S' if with_time else '%Y-%m-%d'
    if hasattr(value, 'strftime'):
        try:
            return value.strftime(fmt)
        except Exception:
            return str(value)
    try:
        n = float(value)
        if n > 1e12:
            n = n / 1000.0
        return datetime.fromtimestamp(n, tz=timezone.utc).strftime(fmt)
    except (TypeError, ValueError, OSError):
        text = str(value)
        return text[:19] if with_time and len(text) >= 19 else text


def quote_error_reason(exc: Exception) -> str:
    text = str(exc or '').lower()
    if '401' in text or 'unauthorized' in text or 'unauth' in text:
        return 'unauthorized'
    if '403' in text or 'no access' in text or 'no quotes' in text:
        return 'no_access'
    return 'error'


def quote_error_message(exc: Exception, fallback: str) -> str:
    reason = quote_error_reason(exc)
    if reason == 'unauthorized':
        return '行情权限不足或凭证失效，盘口暂不可用'
    if reason == 'no_access':
        return '当前账户无该标的行情权限'
    return f'{fallback}: {exc}'


def empty_depth(symbol: str, market: str, *, configured: bool, reason: str, message: str, lb_symbol: str | None = None) -> dict[str, Any]:
    data = {
        'configured': configured,
        'available': False,
        'reason': reason,
        'message': message,
        'symbol': symbol,
        'market': 'CN' if is_cn_market(market, symbol) else market,
        'asks': [],
        'bids': [],
        'last': None,
    }
    if lb_symbol:
        data['lbSymbol'] = lb_symbol
    return data


def empty_trades(symbol: str, market: str, *, configured: bool, reason: str, message: str, lb_symbol: str | None = None) -> dict[str, Any]:
    data = {
        'configured': configured,
        'available': False,
        'reason': reason,
        'message': message,
        'symbol': symbol,
        'market': 'CN' if is_cn_market(market, symbol) else market,
        'trades': [],
    }
    if lb_symbol:
        data['lbSymbol'] = lb_symbol
    return data


def iter_depth_side(raw: Any, *names: str) -> list[Any]:
    if raw is None:
        return []
    for name in names:
        val = getattr(raw, name, None)
        if val:
            return list(val)
    if isinstance(raw, dict):
        for name in names:
            if raw.get(name):
                return list(raw.get(name) or [])
    return []


def iter_trades(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        return list(raw.get('trades') or raw.get('items') or [])
    trades = getattr(raw, 'trades', None)
    if trades:
        return list(trades)
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def map_depth_level(level: Any, side: str) -> dict[str, Any]:
    if isinstance(level, dict):
        price = to_float(level.get('price'))
        volume = to_float(level.get('volume') or level.get('size'))
        order_num = to_float(level.get('orderNum') or level.get('order_num'))
        position = level.get('position')
    else:
        price = to_float(getattr(level, 'price', None))
        volume = to_float(getattr(level, 'volume', None) or getattr(level, 'size', None))
        order_num = to_float(getattr(level, 'order_num', None) or getattr(level, 'orderNum', None))
        position = getattr(level, 'position', None)
    return {
        'position': position,
        'price': price,
        'volume': volume,
        'size': volume,
        'orderNum': order_num,
        'side': side,
    }


def map_trade_side(direction: Any) -> str | None:
    if direction is None or direction == '':
        return None
    raw = getattr(direction, 'value', direction)
    try:
        return {0: 'neutral', 1: 'sell', 2: 'buy'}.get(int(raw))
    except (TypeError, ValueError):
        pass
    text = str(direction).lower()
    if 'up' in text or 'buy' in text:
        return 'buy'
    if 'down' in text or 'sell' in text:
        return 'sell'
    if 'neutral' in text:
        return 'neutral'
    return None


def map_trade(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        price = to_float(item.get('price'))
        volume = to_float(item.get('volume') or item.get('size'))
        ts = item.get('timestamp') or item.get('time')
        direction = item.get('direction')
        trade_type = item.get('tradeType') or item.get('trade_type')
    else:
        price = to_float(getattr(item, 'price', None))
        volume = to_float(getattr(item, 'volume', None) or getattr(item, 'size', None))
        ts = getattr(item, 'timestamp', None) or getattr(item, 'time', None)
        direction = getattr(item, 'direction', None)
        trade_type = getattr(item, 'trade_type', None) or getattr(item, 'tradeType', None)
    return {
        'time': fmt_ts(ts, with_time=True),
        'price': price,
        'volume': volume,
        'size': volume,
        'side': map_trade_side(direction),
        'tradeType': str(trade_type or ''),
    }


def map_candlestick(bar: Any, with_time: bool = False) -> dict[str, Any]:
    if isinstance(bar, dict):
        ts = bar.get('timestamp') or bar.get('date')
        return {
            'date': fmt_ts(ts, with_time=with_time),
            'open': to_float(bar.get('open')),
            'high': to_float(bar.get('high')),
            'low': to_float(bar.get('low')),
            'close': to_float(bar.get('close')),
            'volume': to_float(bar.get('volume')),
        }
    return {
        'date': fmt_ts(getattr(bar, 'timestamp', None), with_time=with_time),
        'open': to_float(getattr(bar, 'open', None)),
        'high': to_float(getattr(bar, 'high', None)),
        'low': to_float(getattr(bar, 'low', None)),
        'close': to_float(getattr(bar, 'close', None)),
        'volume': to_float(getattr(bar, 'volume', None)),
    }


def map_intraday_point(point: Any) -> dict[str, Any]:
    if isinstance(point, dict):
        price = to_float(point.get('price') or point.get('close'))
        ts = point.get('timestamp') or point.get('time')
        volume = to_float(point.get('volume'))
    else:
        price = to_float(getattr(point, 'price', None) or getattr(point, 'close', None))
        ts = getattr(point, 'timestamp', None) or getattr(point, 'time', None)
        volume = to_float(getattr(point, 'volume', None))
    return {
        'date': fmt_ts(ts, with_time=True),
        'open': price,
        'high': price,
        'low': price,
        'close': price,
        'volume': volume,
    }


def assemble_depth(raw: Any, symbol: str, market: str, lb_symbol: str) -> dict[str, Any]:
    asks = [map_depth_level(x, 'ask') for x in iter_depth_side(raw, 'asks', 'ask')]
    bids = [map_depth_level(x, 'bid') for x in iter_depth_side(raw, 'bids', 'bid')]
    asks = [x for x in asks if x.get('price') is not None][:10]
    bids = [x for x in bids if x.get('price') is not None][:10]
    return {
        'configured': True,
        'available': bool(asks or bids),
        'reason': None if (asks or bids) else 'empty',
        'message': None if (asks or bids) else '暂无盘口',
        'symbol': symbol,
        'market': str(market or 'US').upper(),
        'lbSymbol': getattr(raw, 'symbol', None) or lb_symbol,
        'asks': asks,
        'bids': bids,
        'last': None,
    }


def assemble_trades(raw: Any, symbol: str, market: str, lb_symbol: str, count: int) -> dict[str, Any]:
    items = [map_trade(x) for x in iter_trades(raw)]
    items = [x for x in items if x.get('price') is not None]
    items.sort(key=lambda x: str(x.get('time') or ''), reverse=True)
    items = items[: max(1, min(int(count or 30), 100))]
    return {
        'configured': True,
        'available': bool(items),
        'reason': None if items else 'empty',
        'message': None if items else '暂无成交',
        'symbol': symbol,
        'market': str(market or 'US').upper(),
        'lbSymbol': lb_symbol,
        'trades': items,
    }


def overlay_last_bar(bar: dict[str, Any], last: float) -> None:
    """用实时最新价覆盖已有最后一根 K 的 close/high/low，不新增 bar。"""
    if not bar:
        return
    bar['close'] = last
    try:
        high = float(bar['high']) if bar.get('high') is not None else last
        low = float(bar['low']) if bar.get('low') is not None else last
        bar['high'] = max(high, last)
        bar['low'] = min(low, last)
    except (TypeError, ValueError):
        bar['high'] = last
        bar['low'] = last
