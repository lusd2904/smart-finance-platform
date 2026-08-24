"""A 股交易日历：周末 + 已知节假日。港股/美股仅用工作日近似。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo('Asia/Shanghai')
HK_TZ = ZoneInfo('Asia/Hong_Kong')
US_TZ = ZoneInfo('America/New_York')

# date.weekday()：周一=0 … 周六=5，周日=6
WEEKDAY_SATURDAY = 5

# 国务院放假安排（2025–2027 主要休市日，调休上班日不在此表）
CN_HOLIDAYS = {
    date(2025, 1, 1),
    date(2025, 1, 28),
    date(2025, 1, 29),
    date(2025, 1, 30),
    date(2025, 1, 31),
    date(2025, 2, 1),
    date(2025, 2, 2),
    date(2025, 2, 3),
    date(2025, 2, 4),
    date(2025, 4, 4),
    date(2025, 4, 5),
    date(2025, 4, 6),
    date(2025, 5, 1),
    date(2025, 5, 2),
    date(2025, 5, 3),
    date(2025, 5, 4),
    date(2025, 5, 5),
    date(2025, 5, 31),
    date(2025, 6, 1),
    date(2025, 6, 2),
    date(2025, 10, 1),
    date(2025, 10, 2),
    date(2025, 10, 3),
    date(2025, 10, 4),
    date(2025, 10, 5),
    date(2025, 10, 6),
    date(2025, 10, 7),
    date(2025, 10, 8),
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 2, 15),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 21),
    date(2026, 2, 22),
    date(2026, 2, 23),
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 5, 2),
    date(2026, 5, 3),
    date(2026, 5, 4),
    date(2026, 5, 5),
    date(2026, 6, 19),
    date(2026, 6, 20),
    date(2026, 6, 21),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 3),
    date(2026, 10, 4),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
    date(2026, 10, 8),
    date(2027, 1, 1),
}

CN_MAKEUP_WORKDAYS = {
    date(2025, 1, 26),
    date(2025, 2, 8),
    date(2025, 4, 27),
    date(2025, 9, 28),
    date(2025, 10, 11),
    date(2026, 2, 14),
    date(2026, 2, 28),
    date(2026, 9, 27),
    date(2026, 10, 10),
}

SESSION = {
    'CN': (CN_TZ, time(9, 30), time(15, 0)),
    'HK': (HK_TZ, time(9, 30), time(16, 0)),
    'US': (US_TZ, time(9, 30), time(16, 0)),
}


def today_cn(now: datetime | None = None) -> date:
    stamp = now or datetime.now(CN_TZ)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=CN_TZ)
    return stamp.astimezone(CN_TZ).date()


def is_cn_trading_day(day: date | None = None) -> bool:
    day = day or today_cn()
    if day in CN_HOLIDAYS:
        return False
    if day in CN_MAKEUP_WORKDAYS:
        return True
    return is_weekday(day)


def next_cn_trading_day(day: date | None = None) -> date:
    cursor = (day or today_cn()) + timedelta(days=1)
    for _ in range(20):
        if is_cn_trading_day(cursor):
            return cursor
        cursor += timedelta(days=1)
    return cursor


def is_weekday(day: date) -> bool:
    """周一至周五；date.weekday() 周一为 0，5 即周六。"""
    return day.weekday() < WEEKDAY_SATURDAY


def is_market_session_open(market: str, now: datetime | None = None) -> bool:
    """盘中可立即送模拟单；否则排队到下一开盘。"""
    mkt = (market or 'US').upper()
    tz, start, end = SESSION.get(mkt, SESSION['US'])
    stamp = now or datetime.now(tz)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=tz)
    local = stamp.astimezone(tz)
    local_day = local.date()
    if mkt == 'CN' and not is_cn_trading_day(local_day):
        return False
    if mkt != 'CN' and not is_weekday(local_day):
        return False
    current = local.time().replace(tzinfo=None)
    return start <= current <= end
