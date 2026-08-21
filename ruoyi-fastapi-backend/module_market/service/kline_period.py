"""K 线周期归一化：只映射已支持周期，不补造 OHLCV。"""

from __future__ import annotations

_PERIOD_ALIASES = {
    'intraday': 'intraday',
    'timeshare': 'intraday',
    'time': 'intraday',
    'ts': 'intraday',
    '分时': 'intraday',
    '1min': '1min',
    '1m': '1min',
    'min1': '1min',
    '1分': '1min',
    '5min': '5min',
    '5m': '5min',
    'min5': '5min',
    '5分': '5min',
    '15min': '15min',
    '15m': '15min',
    'min15': '15min',
    '15分': '15min',
    'daily': 'daily',
    'day': 'daily',
    'd': 'daily',
    '1d': 'daily',
    '日': 'daily',
    '日k': 'daily',
    'weekly': 'weekly',
    'week': 'weekly',
    'w': 'weekly',
    '1w': 'weekly',
    '周': 'weekly',
    '周k': 'weekly',
    'monthly': 'monthly',
    'month': 'monthly',
    'mo': 'monthly',
    '1mo': 'monthly',
    '月': 'monthly',
    '月k': 'monthly',
}

_MINUTE_PERIODS = frozenset({'intraday', '1min', '5min', '15min'})
_RESAMPLE = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
_DEFAULT_START = {
    'intraday': '-1d',
    '1min': '-2d',
    '5min': '-5d',
    '15min': '-10d',
    'daily': '-2y',
    'weekly': '-3y',
    'monthly': '-5y',
}


def normalize_kline_period(raw: str | None) -> str:
    text = str(raw or 'daily').strip().lower()
    return _PERIOD_ALIASES.get(text, 'daily')


def is_minute_period(period: str | None) -> bool:
    return normalize_kline_period(period) in _MINUTE_PERIODS


def resample_how(period: str | None) -> str | None:
    return _RESAMPLE.get(normalize_kline_period(period))


def default_range_start(period: str | None, current_start: str | None = None) -> str:
    """日K 默认 -2y 时，周/月自动拉长；调用方传入的非默认 start 原样保留。"""
    start = str(current_start or '').strip()
    period_key = normalize_kline_period(period)
    if start and start not in {'-2y', ''}:
        return start
    return _DEFAULT_START.get(period_key, '-2y')
