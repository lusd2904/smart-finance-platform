"""长桥盘口/成交/K线映射。无 SDK、无日志依赖，便于单测。不补造档位或 K 线。"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

CN_NO_DEPTH_MSG = 'A股暂无实时盘口'


def is_cn_market(market: str | None, symbol: str | None = None) -> bool:
    mkt = str(market or '').strip().upper()
    if mkt in {'CN', 'SH', 'SZ', 'A'}:
        return True
    raw = str(symbol or '').strip().upper()
    return raw.endswith(('.SH', '.SZ'))


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_MS_EPOCH = 1e12
_TS_LEN_FULL = 19  # 'YYYY-MM-DD HH:MM:SS'
_RATIO_AS_FRACTION = 0.05


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if hasattr(value, 'strftime'):
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None
    try:
        n = float(value)
        if n > _MS_EPOCH:
            n = n / 1000.0
        return datetime.fromtimestamp(n, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        pass
    try:
        return datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    except Exception:
        return None


def fmt_ts(value: Any, with_time: bool = False, tz_name: str | None = None) -> str:
    if value is None or value == '':
        return ''
    if with_time and not tz_name:
        tz_name = 'Asia/Shanghai'
    fmt = '%Y-%m-%d %H:%M:%S' if with_time else '%Y-%m-%d'
    dt = _as_datetime(value)
    if dt is None:
        if hasattr(value, 'strftime'):
            try:
                return value.strftime(fmt)
            except Exception:
                pass
        text = str(value).strip()
        return text[:_TS_LEN_FULL] if with_time and len(text) >= _TS_LEN_FULL else text
    # 墙上时钟字符串（assemble 会对 fmt_ts 结果二次处理）不得再当 UTC +8
    if tz_name and dt.tzinfo is None and isinstance(value, str):
        return dt.strftime(fmt)
    if tz_name:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        with suppress(Exception):
            dt = dt.astimezone(ZoneInfo(tz_name))
    return dt.strftime(fmt)


def is_auth_denied(exc: BaseException | str | None) -> bool:
    text = str(exc or '')
    lowered = text.lower()
    if '401004' in text or '401003' in text:
        return True
    if '401' in text and ('unauth' in lowered or 'token' in lowered or 'access' in lowered):
        return True
    if 'unauthorized' in lowered or 'unauth' in lowered or 'token invalid' in lowered:
        return True
    if 'token' in lowered and any(word in lowered for word in ('invalid', 'expired', '失效', '过期')):
        return True
    return bool('凭证失效' in text or '令牌无效' in text)


def quote_error_reason(exc: Exception) -> str:
    text = str(exc or '')
    lowered = text.lower()
    if '401004' in text or 'circuit' in lowered:
        return 'circuit_open' if 'circuit' in lowered else 'unauthorized'
    if '401' in text or 'unauthorized' in lowered or 'unauth' in lowered:
        return 'unauthorized'
    if 'timeout' in lowered or 'timed out' in lowered:
        return 'timeout'
    if '403' in lowered or 'no access' in lowered or 'no quotes' in lowered:
        return 'no_access'
    return 'error'


def quote_error_message(exc: Exception, fallback: str) -> str:
    reason = quote_error_reason(exc)
    if reason == 'unauthorized':
        return '行情权限不足或凭证失效，盘口暂不可用'
    if reason == 'no_access':
        return '当前账户无该标的行情权限'
    return f'{fallback}: {exc}'


def empty_depth(
    symbol: str, market: str, *, configured: bool, reason: str, message: str, lb_symbol: str | None = None
) -> dict[str, Any]:
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


def empty_trades(
    symbol: str, market: str, *, configured: bool, reason: str, message: str, lb_symbol: str | None = None
) -> dict[str, Any]:
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
        'time': fmt_ts(ts, with_time=True, tz_name='Asia/Shanghai'),
        'price': price,
        'volume': volume,
        'size': volume,
        'side': map_trade_side(direction),
        'tradeType': str(trade_type or ''),
    }


def map_candlestick(bar: Any, with_time: bool = False, tz_name: str | None = None) -> dict[str, Any]:
    if isinstance(bar, dict):
        ts = bar.get('timestamp') or bar.get('date')
        return {
            'date': fmt_ts(ts, with_time=with_time, tz_name=tz_name),
            'open': to_float(bar.get('open')),
            'high': to_float(bar.get('high')),
            'low': to_float(bar.get('low')),
            'close': to_float(bar.get('close')),
            'volume': to_float(bar.get('volume')),
        }
    return {
        'date': fmt_ts(getattr(bar, 'timestamp', None), with_time=with_time, tz_name=tz_name),
        'open': to_float(getattr(bar, 'open', None)),
        'high': to_float(getattr(bar, 'high', None)),
        'low': to_float(getattr(bar, 'low', None)),
        'close': to_float(getattr(bar, 'close', None)),
        'volume': to_float(getattr(bar, 'volume', None)),
    }


def map_intraday_point(point: Any, tz_name: str | None = None) -> dict[str, Any]:
    if isinstance(point, dict):
        price = to_float(point.get('price') or point.get('close'))
        ts = point.get('timestamp') or point.get('time')
        volume = to_float(point.get('volume'))
    else:
        price = to_float(getattr(point, 'price', None) or getattr(point, 'close', None))
        ts = getattr(point, 'timestamp', None) or getattr(point, 'time', None)
        volume = to_float(getattr(point, 'volume', None))
    return {
        'date': fmt_ts(ts, with_time=True, tz_name=tz_name),
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


def _attr(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for name in names:
            if obj.get(name) is not None:
                return obj.get(name)
        return None
    for name in names:
        val = getattr(obj, name, None)
        if val is not None:
            return val
    return None


def map_static_info(info: Any) -> dict[str, Any]:
    if not info:
        return {}
    return {
        'symbol': _attr(info, 'symbol'),
        'name': _attr(info, 'name_cn', 'nameCn', 'name_en', 'name'),
        'exchange': _attr(info, 'exchange'),
        'currency': _attr(info, 'currency'),
        'lotSize': _attr(info, 'lot_size', 'lotSize'),
        'totalShares': to_float(_attr(info, 'total_shares', 'totalShares')),
        'circulatingShares': to_float(_attr(info, 'circulating_shares', 'circulatingShares')),
        'eps': to_float(_attr(info, 'eps')),
        'epsTtm': to_float(_attr(info, 'eps_ttm', 'epsTtm')),
        'bps': to_float(_attr(info, 'bps')),
        'dividendYield': to_float(_attr(info, 'dividend_yield', 'dividendYield')),
    }


def map_security_quote(quote: Any) -> dict[str, Any]:
    if not quote:
        return {}
    last = to_float(_attr(quote, 'last_done', 'lastDone', 'last'))
    prev_close = to_float(_attr(quote, 'prev_close', 'prevClose'))
    change = change_rate = None
    if last is not None and prev_close not in (None, 0):
        change = round(last - prev_close, 4)
        change_rate = round(change / prev_close * 100, 4)
    return {
        'symbol': _attr(quote, 'symbol'),
        'last': last,
        'prevClose': prev_close,
        'open': to_float(_attr(quote, 'open')),
        'high': to_float(_attr(quote, 'high')),
        'low': to_float(_attr(quote, 'low')),
        'volume': to_float(_attr(quote, 'volume')),
        'turnover': to_float(_attr(quote, 'turnover')),
        'change': change,
        'changeRate': change_rate,
        'timestamp': fmt_ts(_attr(quote, 'timestamp'), with_time=True),
        'tradeStatus': str(_attr(quote, 'trade_status', 'tradeStatus') or ''),
    }


def map_calc_index(row: Any) -> dict[str, Any]:
    if not row:
        return {}
    return {
        'peTtm': to_float(_attr(row, 'pe_ttm_ratio', 'peTtmRatio')),
        'pb': to_float(_attr(row, 'pb_ratio', 'pbRatio')),
        'marketCap': to_float(_attr(row, 'total_market_value', 'totalMarketValue')),
        'turnoverRate': to_float(_attr(row, 'turnover_rate', 'turnoverRate')),
        'volumeRatio': to_float(_attr(row, 'volume_ratio', 'volumeRatio')),
        'amplitude': to_float(_attr(row, 'amplitude')),
        'turnover': to_float(_attr(row, 'turnover')),
        'volume': to_float(_attr(row, 'volume')),
        'last': to_float(_attr(row, 'last_done', 'lastDone')),
        'changeRate': to_float(_attr(row, 'change_rate', 'changeRate')),
        'change': to_float(_attr(row, 'change_value', 'changeValue')),
        'dividendYieldTtm': to_float(_attr(row, 'dividend_ratio_ttm', 'dividendRatioTtm')),
        'capitalFlow': to_float(_attr(row, 'capital_flow', 'capitalFlow')),
    }


def map_capital_bucket(part: Any) -> dict[str, float | None]:
    return {
        'large': to_float(_attr(part, 'large')),
        'medium': to_float(_attr(part, 'medium')),
        'small': to_float(_attr(part, 'small')),
    }


def map_capital_distribution(resp: Any) -> dict[str, Any]:
    if not resp:
        return {}
    incoming = map_capital_bucket(_attr(resp, 'capital_in', 'capitalIn'))
    outgoing = map_capital_bucket(_attr(resp, 'capital_out', 'capitalOut'))

    def _sum(bucket: dict[str, float | None]) -> float:
        return sum(v or 0 for v in bucket.values())

    return {
        'in': incoming,
        'out': outgoing,
        'net': _sum(incoming) - _sum(outgoing),
        'timestamp': fmt_ts(_attr(resp, 'timestamp'), with_time=True),
    }


def map_news_item(item: Any) -> dict[str, Any] | None:
    if not item:
        return None
    title = _attr(item, 'title', 'headline', 'title_cn')
    if not title:
        return None
    published = _attr(item, 'published_at', 'publishedAt', 'time')
    return {
        'id': str(_attr(item, 'id') or title),
        'title': str(title),
        'source': str(_attr(item, 'source') or '长桥'),
        'url': str(_attr(item, 'url') or ''),
        'time': fmt_ts(published, with_time=True) if published else '',
        'summary': str(_attr(item, 'description', 'summary') or '')[:180],
    }


def kline_high_low(klines: list[dict[str, Any]] | None) -> tuple[float | None, float | None]:
    highs = [to_float(row.get('high')) for row in (klines or [])]
    lows = [to_float(row.get('low')) for row in (klines or [])]
    highs = [v for v in highs if v not in (None, 0)]
    lows = [v for v in lows if v not in (None, 0)]
    return (max(highs) if highs else None, min(lows) if lows else None)


def assemble_quote_snapshot(  # noqa: PLR0915
    *,
    symbol: str,
    market: str,
    lb_symbol: str,
    quote: dict[str, Any] | None,
    static: dict[str, Any] | None,
    calc: dict[str, Any] | None,
    capital: dict[str, Any] | None,
    high52: float | None = None,
    low52: float | None = None,
) -> dict[str, Any]:
    """拼终端快照：长桥 quote + static_info + calc_indexes，缺省用现价/股本推导。"""
    quote = quote or {}
    static = static or {}
    calc = calc or {}
    last = to_float(calc.get('last')) or to_float(quote.get('last'))
    prev_close = to_float(quote.get('prevClose'))
    high = to_float(quote.get('high'))
    low = to_float(quote.get('low'))
    turnover = to_float(calc.get('turnover')) or to_float(quote.get('turnover'))
    volume = to_float(calc.get('volume')) or to_float(quote.get('volume'))
    total_shares = to_float(static.get('totalShares'))
    circ_shares = to_float(static.get('circulatingShares'))
    eps = to_float(static.get('eps'))
    eps_ttm = to_float(static.get('epsTtm'))
    bps = to_float(static.get('bps'))

    pe = to_float(calc.get('peTtm'))
    if pe is None and last and eps_ttm not in (None, 0):
        pe = round(last / eps_ttm, 4)
    pe_static = None
    if last and eps not in (None, 0):
        pe_static = round(last / eps, 4)
    pb = to_float(calc.get('pb'))
    if pb is None and last and bps not in (None, 0):
        pb = round(last / bps, 4)
    market_cap = to_float(calc.get('marketCap'))
    if market_cap is None and last and total_shares:
        market_cap = last * total_shares
    float_mcap = last * circ_shares if last and circ_shares else None
    turnover_rate = to_float(calc.get('turnoverRate'))
    if turnover_rate is None and turnover and last and circ_shares:
        denom = last * circ_shares
        if denom:
            turnover_rate = turnover / denom
    amplitude = to_float(calc.get('amplitude'))
    if amplitude is None and high is not None and low is not None and prev_close not in (None, 0):
        amplitude = (high - low) / prev_close
    avg_price = (turnover / volume) if turnover and volume else None
    if turnover_rate is not None and abs(turnover_rate) <= _RATIO_AS_FRACTION:
        turnover_rate = turnover_rate * 100
    if amplitude is not None and abs(amplitude) <= _RATIO_AS_FRACTION:
        amplitude = amplitude * 100
    dy = to_float(calc.get('dividendYieldTtm')) or to_float(static.get('dividendYield'))
    dy_ratio = None
    if dy is not None:
        dy_ratio = dy if abs(dy) <= _RATIO_AS_FRACTION else dy / 100.0
    dividend_ttm = (last * dy_ratio) if last and dy_ratio is not None else None
    dy_percent = (dy_ratio * 100) if dy_ratio is not None else None

    cap = capital or {}
    if not cap and calc.get('capitalFlow') is not None:
        cap = {'net': to_float(calc.get('capitalFlow')), 'in': {}, 'out': {}}

    available = bool(last or pe or market_cap or quote)
    return {
        'configured': True,
        'available': available,
        'symbol': symbol,
        'market': str(market or 'US').upper(),
        'lbSymbol': lb_symbol,
        'quote': quote,
        'static': static,
        'calc': calc,
        'capital': cap,
        'peTtm': pe,
        'peStatic': pe_static,
        'pb': pb,
        'marketCap': market_cap,
        'floatMarketCap': float_mcap,
        'turnoverRate': turnover_rate,
        'volumeRatio': to_float(calc.get('volumeRatio')),
        'amplitude': amplitude,
        'avgPrice': avg_price,
        'dividendYield': dy_percent if dy_percent is not None else dy,
        'dividendTtm': dividend_ttm,
        'lotSize': static.get('lotSize'),
        'currency': static.get('currency') or quote.get('currency'),
        'name': static.get('name'),
        'last': last,
        'open': to_float(quote.get('open')),
        'high': high,
        'low': low,
        'prevClose': prev_close,
        'volume': volume,
        'turnover': turnover,
        'change': to_float(quote.get('change')) or to_float(calc.get('change')),
        'changeRate': to_float(quote.get('changeRate')) or to_float(calc.get('changeRate')),
        'high52': to_float(high52),
        'low52': to_float(low52),
        'historyHigh': None,
        'historyLow': None,
        'peDynamic': None,
        'beta': None,
        'timestamp': fmt_ts(quote.get('timestamp'), with_time=True) if quote.get('timestamp') else '',
    }


def merge_snapshot_with_db(snap: dict[str, Any] | None, db: dict[str, Any] | None) -> dict[str, Any]:
    """页面字段：库里有的补空缺，库没有的保留长桥。不覆盖长桥已给出的实时价/估值。"""
    out = dict(snap or {})
    for key, val in (db or {}).items():
        if val is None or val == '':
            continue
        cur = out.get(key)
        if cur is None or cur == '':
            out[key] = val
    if not out.get('available'):
        out['available'] = bool(
            out.get('last') or out.get('peTtm') or out.get('marketCap') or out.get('historyHigh') or out.get('high52')
        )
    return out
