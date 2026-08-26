"""三市场交易时段：美股始终展示；港股 / A 股仅当地盘中。

`is_in_session` / `should_include_market` 仍按常规盘（美股 09:30–16:00 ET）判断指数顶栏。
K 线实时源用 `us_session_tag` / `is_live_kline_session`：美股工作日含盘前/盘后/夜盘。
"""

from __future__ import annotations

from datetime import datetime
from datetime import time as dt_time
from zoneinfo import ZoneInfo

_SATURDAY_WEEKDAY = 5
_US_PRE = dt_time(4, 0)
_US_REGULAR = dt_time(9, 30)
_US_POST = dt_time(16, 0)
_US_OVERNIGHT = dt_time(20, 0)

SESSIONS: dict[str, list[tuple[dt_time, dt_time]]] = {
    'CN': [(dt_time(9, 30), dt_time(11, 30)), (dt_time(13, 0), dt_time(15, 0))],
    'HK': [(dt_time(9, 30), dt_time(12, 0)), (dt_time(13, 0), dt_time(16, 0))],
    'US': [(dt_time(9, 30), dt_time(16, 0))],
}

MARKET_TZ = {'CN': 'Asia/Shanghai', 'HK': 'Asia/Hong_Kong', 'US': 'America/New_York'}


def is_in_session(market: str, now_local: datetime) -> bool:
    """按市场时区判断当前是否处于常规交易时段（工作日 + 时段内）。"""
    if now_local.weekday() >= _SATURDAY_WEEKDAY:
        return False
    current = now_local.time()
    windows = SESSIONS.get(str(market or '').upper()) or []
    return any(start <= current < end for start, end in windows)


def should_include_market(market: str, now_local: datetime) -> bool:
    """顶栏：美股始终展示；港股 / A 股仅当地盘中。"""
    if str(market or '').upper() == 'US':
        return True
    return is_in_session(market, now_local)


def us_session_tag(now_et: datetime) -> str:
    """美股会话：overnight | pre | regular | post | closed（周末）。时间为美东。"""
    if now_et.weekday() >= _SATURDAY_WEEKDAY:
        return 'closed'
    current = now_et.time()
    if _US_PRE <= current < _US_REGULAR:
        return 'pre'
    if _US_REGULAR <= current < _US_POST:
        return 'regular'
    if _US_POST <= current < _US_OVERNIGHT:
        return 'post'
    return 'overnight'


def _now_in_market(market: str, now: datetime | None = None) -> datetime:
    tz_name = MARKET_TZ.get(str(market or '').upper())
    if tz_name is None:
        return now if now is not None else datetime.now()
    tz = ZoneInfo(tz_name)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def kline_session_tag(market: str, now: datetime | None = None) -> str:
    """K 线用会话标签：美股五段；港股/A 股 regular 或 closed。"""
    mkt = str(market or '').upper()
    now_local = _now_in_market(mkt, now)
    if mkt == 'US':
        return us_session_tag(now_local)
    if mkt in MARKET_TZ:
        return 'regular' if is_in_session(mkt, now_local) else 'closed'
    return 'closed'


def is_live_kline_session(market: str, now: datetime | None = None) -> bool:
    """分钟/分时是否走实时 K：美股工作日任一盘段；港股/A 股仅当地常规开盘。"""
    mkt = str(market or '').upper()
    now_local = _now_in_market(mkt, now)
    if mkt == 'US':
        return us_session_tag(now_local) != 'closed'
    return is_in_session(mkt, now_local)
