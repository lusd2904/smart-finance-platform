"""
技术指标计算服务：基于纯 pandas 实现常用技术指标（不依赖 pandas_ta，兼容 Python 3.10/3.11 镜像）。
返回结构化 dict（含日期轴 dates 与各指标序列），供前端叠加绘图。
NaN 统一转为 None，方便 JSON 序列化与前端处理。
"""

from typing import Any

import pandas as pd

from utils.log_util import logger


def _series_to_list(s: pd.Series | None) -> list[float | None]:
    """把pandas Series转为list，NaN->None，float化。"""
    if s is None:
        return []
    return [None if pd.isna(v) else float(v) for v in s.tolist()]


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()


def _kdj(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 9, signal: int = 3):
    lowest = low.rolling(length).min()
    highest = high.rolling(length).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, pd.NA) * 100
    k = rsv.ewm(alpha=1 / signal, adjust=False).mean()
    d = k.ewm(alpha=1 / signal, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tp = (high + low + close) / 3
    ma = tp.rolling(length).mean()
    md = (tp - ma).abs().rolling(length).mean()
    return (tp - ma) / (0.015 * md.replace(0, pd.NA))


def _willr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    highest = high.rolling(length).max()
    lowest = low.rolling(length).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, pd.NA)


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * volume.fillna(0)).cumsum()


class IndicatorService:
    """
    技术指标计算服务
    """

    @classmethod
    def _to_dataframe(cls, klines: list[dict[str, Any]]) -> pd.DataFrame:
        """
        把 [{date,open,high,low,close,volume}] 升序K线转为DataFrame。
        """
        df = pd.DataFrame(klines)
        if df.empty:
            return df
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        for col in ('open', 'high', 'low', 'close', 'volume'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    @classmethod
    def calculate(cls, klines: list[dict[str, Any]]) -> dict[str, Any]:
        """
        计算全部常用技术指标。
        """
        df = cls._to_dataframe(klines)
        if df.empty:
            return {'dates': []}

        close, high, low = df['close'], df['high'], df['low']
        volume = df['volume'] if 'volume' in df.columns else None
        dates = df['date'].dt.strftime('%Y-%m-%d').tolist()
        result: dict[str, Any] = {'dates': dates}

        try:
            result['ma'] = {f'ma{p}': _series_to_list(close.rolling(p).mean()) for p in (5, 10, 20, 60)}
            ema12 = _ema(close, 12)
            ema26 = _ema(close, 26)
            result['ema'] = {
                'ema12': _series_to_list(ema12),
                'ema26': _series_to_list(ema26),
            }
            dif = ema12 - ema26
            dea = _ema(dif, 9)
            hist = 2 * (dif - dea)
            result['macd'] = {
                'dif': _series_to_list(dif),
                'dea': _series_to_list(dea),
                'macd': _series_to_list(hist),
            }
            result['rsi'] = {
                'rsi6': _series_to_list(_rsi(close, 6)),
                'rsi12': _series_to_list(_rsi(close, 12)),
                'rsi24': _series_to_list(_rsi(close, 24)),
            }
            k, d, j = _kdj(high, low, close)
            result['kdj'] = {'k': _series_to_list(k), 'd': _series_to_list(d), 'j': _series_to_list(j)}
            mid = close.rolling(20).mean()
            std = close.rolling(20).std()
            result['boll'] = {
                'upper': _series_to_list(mid + 2 * std),
                'mid': _series_to_list(mid),
                'lower': _series_to_list(mid - 2 * std),
            }
            result['atr'] = _series_to_list(_atr(high, low, close, 14))
            result['cci'] = _series_to_list(_cci(high, low, close, 14))
            result['wr'] = _series_to_list(_willr(high, low, close, 14))
            if volume is not None:
                result['obv'] = _series_to_list(_obv(close, volume))
                result['volMa'] = {
                    'volMa5': _series_to_list(volume.rolling(5).mean()),
                    'volMa10': _series_to_list(volume.rolling(10).mean()),
                }
            else:
                result['obv'] = []
                result['volMa'] = {'volMa5': [], 'volMa10': []}
        except Exception as e:
            logger.error(f'[行情指标] 计算失败: {e}')
            raise

        return result

    @classmethod
    def latest_snapshot(cls, klines: list[dict[str, Any]]) -> dict[str, Any]:
        """
        计算最新一日的关键指标快照。
        """
        full = cls.calculate(klines)
        if not full.get('dates'):
            return {}

        def last(seq: list[Any] | None) -> Any:
            if not seq:
                return None
            return seq[-1]

        snap: dict[str, Any] = {'date': full['dates'][-1]}
        if klines:
            snap['close'] = klines[-1].get('close')
        snap['ma'] = {k: last(v) for k, v in (full.get('ma') or {}).items()}
        snap['macd'] = {k: last(v) for k, v in (full.get('macd') or {}).items()}
        snap['rsi'] = {k: last(v) for k, v in (full.get('rsi') or {}).items()}
        snap['kdj'] = {k: last(v) for k, v in (full.get('kdj') or {}).items()}
        snap['boll'] = {k: last(v) for k, v in (full.get('boll') or {}).items()}
        snap['atr'] = last(full.get('atr'))
        snap['cci'] = last(full.get('cci'))
        snap['wr'] = last(full.get('wr'))
        return snap
