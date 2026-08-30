"""
WorldQuant Alpha101 + Microsoft Qlib Alpha158 高阶因子引擎。

单标的时序实现：原文中的截面 rank() 退化为滚动时序分位（ts_rank）。
只依赖 OHLCV；VWAP 用典型价格 (H+L+C)/3 近似。
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

ALPHA_ENGINE_VERSION = 'alpha-101-158-v1'
ALPHA101_WINDOWS_NEED = 60
ALPHA158_WINDOWS = (5, 10, 20, 30, 60)


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _last(series: pd.Series | None, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default
    return _finite(series.iloc[-1], default)


def _prep(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or len(df) < 20:
        return None
    out = df.copy()
    for col in ('open', 'high', 'low', 'close', 'volume'):
        if col not in out.columns:
            return None
        out[col] = pd.to_numeric(out[col], errors='coerce')
    out = out.dropna(subset=['open', 'high', 'low', 'close'])
    if len(out) < 20:
        return None
    out['volume'] = out['volume'].fillna(0.0).clip(lower=0.0)
    out['vwap'] = (out['high'] + out['low'] + out['close']) / 3.0
    out['returns'] = out['close'].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out


def _minp(window: int, floor: int = 2) -> int:
    window = max(int(window), 1)
    return max(1, min(window, max(floor, window // 2)))


def _delta(series: pd.Series, period: int = 1) -> pd.Series:
    return series.diff(period)


def _delay(series: pd.Series, period: int = 1) -> pd.Series:
    return series.shift(period)


def _ts_sum(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=_minp(window)).sum()


def _ts_mean(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=_minp(window)).mean()


def _ts_std(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=_minp(window, 2)).std()


def _ts_min(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=_minp(window)).min()


def _ts_max(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=_minp(window)).max()


def _ts_corr(left: pd.Series, right: pd.Series, window: int) -> pd.Series:
    return left.rolling(window, min_periods=_minp(window, 2)).corr(right)


def _ts_cov(left: pd.Series, right: pd.Series, window: int) -> pd.Series:
    return left.rolling(window, min_periods=_minp(window, 2)).cov(right)


def _as_float_array(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors='coerce').to_numpy(dtype=float, copy=False)


def _ts_rank(series: pd.Series, window: int = 20) -> pd.Series:
    values = _as_float_array(series)
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    min_periods = _minp(window)
    if n >= window:
        views = sliding_window_view(values, window)
        out[window - 1 :] = (views <= views[:, -1:]).sum(axis=1) / float(window)
    for i in range(min_periods - 1, min(window - 1, n)):
        arr = values[max(0, i + 1 - window) : i + 1]
        if arr.size == 0 or not np.isfinite(values[i]):
            continue
        out[i] = float(np.searchsorted(np.sort(arr), arr[-1], side='right') / max(arr.size, 1))
    return pd.Series(out, index=series.index)


def _ts_argmax(series: pd.Series, window: int) -> pd.Series:
    values = _as_float_array(series)
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    min_periods = _minp(window)
    if n >= window:
        out[window - 1 :] = sliding_window_view(values, window).argmax(axis=1)
    for i in range(min_periods - 1, min(window - 1, n)):
        arr = values[max(0, i + 1 - window) : i + 1]
        if arr.size:
            out[i] = float(np.argmax(arr))
    return pd.Series(out, index=series.index)


def _ts_argmin(series: pd.Series, window: int) -> pd.Series:
    values = _as_float_array(series)
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    min_periods = _minp(window)
    if n >= window:
        out[window - 1 :] = sliding_window_view(values, window).argmin(axis=1)
    for i in range(min_periods - 1, min(window - 1, n)):
        arr = values[max(0, i + 1 - window) : i + 1]
        if arr.size:
            out[i] = float(np.argmin(arr))
    return pd.Series(out, index=series.index)


def _window_slope(arr: np.ndarray) -> float:
    if arr.size < 3 or np.allclose(arr, arr[0]):
        return 0.0
    x = np.arange(arr.size, dtype=float)
    x = x - x.mean()
    y = arr - arr.mean()
    denom = float(np.dot(x, x))
    if denom == 0:
        return 0.0
    return float(np.dot(x, y) / denom)


def _window_rsquare(arr: np.ndarray) -> float:
    if arr.size < 3 or np.allclose(arr, arr[0]):
        return 0.0
    x = np.arange(arr.size, dtype=float)
    x = x - x.mean()
    y = arr - arr.mean()
    denom = float(np.dot(x, x) * np.dot(y, y))
    if denom <= 0:
        return 0.0
    return float((np.dot(x, y) ** 2) / denom)


def _slope(series: pd.Series, window: int) -> pd.Series:
    values = _as_float_array(series)
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    min_periods = _minp(window, 3)
    x = np.arange(window, dtype=float)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if n >= window and denom:
        views = sliding_window_view(values, window)
        ok = np.isfinite(views).all(axis=1)
        tail = np.full(len(views), np.nan, dtype=float)
        if ok.any():
            good = views[ok]
            centered = good - good.mean(axis=1, keepdims=True)
            constant = np.all(np.isclose(good, good[:, :1]), axis=1)
            tail[ok] = np.where(constant, 0.0, (centered @ x) / denom)
        out[window - 1 :] = tail
    for i in range(min_periods - 1, min(window - 1, n)):
        out[i] = _window_slope(values[max(0, i + 1 - window) : i + 1])
    return pd.Series(out, index=series.index)


def _rsquare(series: pd.Series, window: int) -> pd.Series:
    values = _as_float_array(series)
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    min_periods = _minp(window, 3)
    x = np.arange(window, dtype=float)
    x = x - x.mean()
    xx = float(np.dot(x, x))
    if n >= window and xx:
        views = sliding_window_view(values, window)
        ok = np.isfinite(views).all(axis=1)
        tail = np.full(len(views), np.nan, dtype=float)
        if ok.any():
            good = views[ok]
            y = good - good.mean(axis=1, keepdims=True)
            yy = np.einsum('ij,ij->i', y, y)
            xy = y @ x
            denom = xx * yy
            rsq = np.divide(xy * xy, denom, out=np.zeros(ok.sum()), where=denom > 0)
            constant = np.all(np.isclose(good, good[:, :1]), axis=1)
            tail[ok] = np.where(constant, 0.0, rsq)
        out[window - 1 :] = tail
    for i in range(min_periods - 1, min(window - 1, n)):
        out[i] = _window_rsquare(values[max(0, i + 1 - window) : i + 1])
    return pd.Series(out, index=series.index)


def _tail(series: pd.Series, window: int) -> pd.Series:
    if window <= 0 or len(series) == 0:
        return series.iloc[0:0]
    return series.iloc[-min(int(window), len(series)) :]


def _last_mean(series: pd.Series, window: int, floor: int = 2) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window, floor):
        return 0.0
    return _finite(chunk.mean())


def _last_slope(series: pd.Series, window: int) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window, 3):
        return 0.0
    return _window_slope(_as_float_array(chunk))


def _last_rsquare(series: pd.Series, window: int) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window, 3):
        return 0.0
    return _window_rsquare(_as_float_array(chunk))


def _last_std(series: pd.Series, window: int) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window, 2):
        return 0.0
    return _finite(chunk.std())


def _last_sum(series: pd.Series, window: int) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window):
        return 0.0
    return _finite(chunk.sum())


def _last_minmax(series: pd.Series, window: int, how: str) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window):
        return 0.0
    return _finite(chunk.max() if how == 'max' else chunk.min())


def _last_quantile(series: pd.Series, window: int, q: float) -> float:
    chunk = _tail(series, window)
    if len(chunk) < max(3, window // 2):
        return 0.0
    return _finite(chunk.quantile(q))


def _last_rank(series: pd.Series, window: int) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window):
        return 0.0
    arr = chunk.to_numpy(dtype=float)
    return float(np.searchsorted(np.sort(arr), arr[-1], side='right') / max(arr.size, 1))


def _last_corr(left: pd.Series, right: pd.Series, window: int) -> float:
    a = _tail(left, window)
    b = _tail(right, window)
    if len(a) < _minp(window, 2):
        return 0.0
    return _finite(a.corr(b))


def _last_arg(series: pd.Series, window: int, how: str) -> float:
    chunk = _tail(series, window)
    if len(chunk) < _minp(window):
        return 0.0
    arr = chunk.to_numpy(dtype=float)
    return float(np.argmax(arr) if how == 'max' else np.argmin(arr))


def _ts_scale(series: pd.Series) -> pd.Series:
    denom = series.abs().rolling(20, min_periods=5).sum().replace(0, np.nan)
    return series / denom


def compute_alpha101(df: pd.DataFrame) -> dict[str, float]:
    """计算可在单标的 OHLCV 上落地的 Alpha101 子集（时序 rank）。"""
    frame = _prep(df)
    if frame is None:
        return {}

    o = frame['open']
    h = frame['high']
    low = frame['low']
    c = frame['close']
    v = frame['volume'] + 1e-12
    vw = frame['vwap']
    r = frame['returns']
    adv20 = _ts_mean(frame['volume'], 20)

    out: dict[str, float] = {}

    def put(code: str, series: pd.Series | float) -> None:
        if isinstance(series, pd.Series):
            out[code] = round(_last(series), 6)
        else:
            out[code] = round(_finite(series), 6)

    try:
        signed = np.where(r < 0, _ts_std(r, 20), c)
        put('alpha001', _ts_rank(pd.Series(signed, index=c.index).pow(2.0).clip(upper=1e6), 5) - 0.5)
    except Exception:
        out['alpha001'] = 0.0

    log_v = pd.Series(np.log(v.to_numpy()), index=v.index)
    put('alpha002', -1 * _ts_corr(_ts_rank(_delta(log_v, 2), 6), _ts_rank((c - o) / (o + 1e-12), 6), 6))
    put('alpha003', -1 * _ts_corr(_ts_rank(o), _ts_rank(v), 10))
    put('alpha004', -1 * _ts_rank(_ts_rank(low), 9))
    put('alpha005', _ts_rank(o - _ts_mean(vw, 10)) * (-1 * (_ts_rank(c - vw)).abs()))
    put('alpha006', -1 * _ts_corr(o, v, 10))
    cond7 = adv20 < frame['volume']
    a7 = -1 * _ts_rank(_delta(c, 7).abs(), 60) * np.sign(_delta(c, 7))
    put('alpha007', pd.Series(np.where(cond7, a7, -1.0), index=c.index))
    inner8 = _ts_sum(o, 5) * _ts_sum(r, 5)
    put('alpha008', -1 * _ts_rank(inner8 - _delay(inner8, 10)))
    d1 = _delta(c, 1)
    put(
        'alpha009',
        pd.Series(
            np.where(
                _ts_min(d1, 5) > 0,
                d1,
                np.where(_ts_max(d1, 5) < 0, d1, -1 * d1),
            ),
            index=c.index,
        ),
    )
    put(
        'alpha010',
        pd.Series(
            np.where(_ts_min(d1, 4) > 0, d1, np.where(_ts_max(d1, 4) < 0, d1, -1 * d1)),
            index=c.index,
        ),
    )
    put('alpha012', np.sign(_delta(v, 1)) * (-1 * _delta(c, 1)))
    put('alpha013', -1 * _ts_rank(_ts_cov(_ts_rank(c), _ts_rank(v), 5)))
    put('alpha014', (-1 * _ts_rank(_delta(r, 3))) * _ts_corr(o, v, 10))
    put('alpha015', -1 * _ts_mean(_ts_corr(_ts_rank(h), _ts_rank(v), 3), 3))
    put('alpha016', -1 * _ts_rank(_ts_cov(_ts_rank(h), _ts_rank(v), 5)))
    put(
        'alpha017',
        (-1 * _ts_rank(_ts_rank(c), 10)) * _ts_rank(_delta(c, 1), 3) * _ts_rank(_delta(v, 1) / v, 10),
    )
    put('alpha018', -1 * _ts_rank(_ts_std(abs(c - o), 5) + (c - o) + _ts_corr(c, o, 10)))
    put('alpha019', (-1 * np.sign(c - _delay(c, 7) + _delta(c, 7))) * (1 + _ts_rank(1 + _ts_sum(r, 250).fillna(0), 10)))
    put('alpha020', (-1 * _ts_rank(o - _delay(h, 1))) * _ts_rank(o - _delay(c, 1)) * _ts_rank(o - _delay(low, 1)))
    put(
        'alpha021',
        pd.Series(
            np.where(
                (_ts_mean(c, 8) + _ts_std(c, 8)) < _ts_mean(c, 2),
                -1,
                np.where(_ts_mean(c, 2) < (_ts_mean(c, 8) - _ts_std(c, 8)), 1, np.where(v / adv20 >= 1, 1, -1)),
            ),
            index=c.index,
        ),
    )
    put('alpha022', -1 * _delta(_ts_corr(h, v, 5), 5) * _ts_rank(_ts_std(c, 20)))
    put(
        'alpha023',
        pd.Series(np.where(_ts_mean(h, 20) < h, -1 * _delta(h, 2), 0.0), index=c.index),
    )
    put(
        'alpha024',
        pd.Series(
            np.where(
                _delta(_ts_mean(c, 100), 100) / _delay(c, 100).abs().clip(lower=1e-9) <= 0.05,
                -1 * (c - _ts_min(c, 100)),
                -1 * _delta(c, 3),
            ),
            index=c.index,
        ),
    )
    put('alpha026', -1 * _ts_max(_ts_corr(_ts_rank(v), _ts_rank(h), 5), 3))
    put('alpha028', _ts_scale(_ts_corr(adv20, low, 5) + (h + low) / 2 - c))
    put('alpha033', _ts_rank(-1 * (1 - o / (c + 1e-12))))
    put('alpha034', _ts_rank(1 - _ts_rank(_ts_std(r, 2) / (_ts_std(r, 5) + 1e-12))) + (1 - _ts_rank(_delta(c, 1))))
    put('alpha035', _ts_rank(v) * (1 - _ts_rank(c + h - low)) * (1 - _ts_rank(r)))
    put('alpha037', _ts_rank(_ts_corr(_delay(o - c, 1), c, 200)) + _ts_rank(o - c))
    put('alpha038', -1 * _ts_rank(_ts_rank(c).diff(7)) * _ts_rank(_ts_corr(vw, _delay(c, 5), 230)))
    put('alpha040', -1 * _ts_rank(_ts_std(h, 10)) * _ts_corr(h, v, 10))
    put('alpha041', ((h * low).pow(0.5) - vw) )
    put('alpha042', _ts_rank(vw - c) / (_ts_rank(vw + c) + 1e-12))
    put('alpha043', _ts_rank(frame['volume'] / (adv20 + 1e-12), 20) * _ts_rank(-1 * _delta(c, 7), 8))
    put('alpha044', -1 * _ts_corr(h, _ts_rank(v), 5))
    put('alpha045', -1 * _ts_rank(_ts_mean(_delay(c, 5), 20)) * _ts_corr(c, v, 2) * _ts_rank(_ts_corr(_ts_sum(c, 5), _ts_sum(c, 20), 2)))
    put(
        'alpha046',
        pd.Series(
            np.where(
                (_delay(c, 20) - _delay(c, 10)) / 10 - (_delay(c, 10) - c) / 10 > 0.25,
                -1,
                np.where((_delay(c, 20) - _delay(c, 10)) / 10 - (_delay(c, 10) - c) / 10 < 0, 1, -1 * (c - _delay(c, 1))),
            ),
            index=c.index,
        ),
    )
    put('alpha049', pd.Series(np.where((_delay(c, 20) - _delay(c, 10)) / 10 - (_delay(c, 10) - c) / 10 < -0.1, 1, -1 * (c - _delay(c, 1))), index=c.index))
    put('alpha052', (-1 * _delta(_ts_min(low, 5), 5)) * _ts_rank(((_ts_sum(r, 240) - _ts_sum(r, 20)) / 220)) * _ts_rank(v))
    close5 = c.clip(lower=1e-6) ** 5
    open5 = o.clip(lower=1e-6) ** 5
    denom54 = (low - h) * close5
    put('alpha054', -1 * ((low - c) * open5) / denom54.replace(0, np.nan))
    put('alpha055', -1 * _ts_corr(_ts_rank((c - _ts_min(low, 12)) / (_ts_max(h, 12) - _ts_min(low, 12) + 1e-12)), _ts_rank(v), 6))
    put('alpha060', -1 * ((2 * _ts_scale(_ts_rank(((((c - low) - (h - c)) / (h - low + 1e-12)) * v)))) - _ts_scale(_ts_rank(_ts_argmax(c, 10)))))
    put('alpha101', (c - o) / ((h - low) + 0.001))

    return out


def compute_alpha158(df: pd.DataFrame) -> dict[str, float]:
    """Qlib Alpha158 风格特征：K 线形态 + 价量相对值 + 多窗口滚动算子。

    特征不互相嵌套，只取末根，因此只算最后窗口，与整段 rolling 取末值同口径。
    """
    frame = _prep(df)
    if frame is None:
        return {}

    o = frame['open']
    h = frame['high']
    low = frame['low']
    c = frame['close']
    v = frame['volume']
    vw = frame['vwap']
    prev = _delay(c, 1)
    chg = c - prev
    n = len(c)
    last_o = float(o.iloc[-1])
    last_h = float(h.iloc[-1])
    last_low = float(low.iloc[-1])
    last_c = float(c.iloc[-1])
    last_v = float(v.iloc[-1])
    last_c_safe = last_c + 1e-12
    last_o_safe = last_o + 1e-12
    rng = last_h - last_low
    out: dict[str, float] = {}

    def put(name: str, value: Any) -> None:
        out[name] = round(_finite(value), 6)

    put('KMID', (last_c - last_o) / last_o_safe)
    put('KLEN', (last_h - last_low) / last_o_safe)
    put('KMID2', (last_c - last_o) / (rng + 1e-12))
    put('KUP', (last_h - max(last_o, last_c)) / last_o_safe)
    put('KUP2', (last_h - max(last_o, last_c)) / (rng + 1e-12))
    put('KLOW', (min(last_o, last_c) - last_low) / last_o_safe)
    put('KLOW2', (min(last_o, last_c) - last_low) / (rng + 1e-12))
    put('KSFT', (2 * last_c - last_h - last_low) / last_o_safe)
    put('KSFT2', (2 * last_c - last_h - last_low) / (rng + 1e-12))

    for lag in range(0, 5):
        if n > lag:
            put(f'OPEN{lag}', float(o.iloc[-1 - lag]) / last_c_safe)
            put(f'HIGH{lag}', float(h.iloc[-1 - lag]) / last_c_safe)
            put(f'LOW{lag}', float(low.iloc[-1 - lag]) / last_c_safe)
            put(f'VWAP{lag}', float(vw.iloc[-1 - lag]) / last_c_safe)
            put(f'VOLUME{lag}', float(v.iloc[-1 - lag]) / (last_v + 1e-12))
        else:
            put(f'OPEN{lag}', 0.0)
            put(f'HIGH{lag}', 0.0)
            put(f'LOW{lag}', 0.0)
            put(f'VWAP{lag}', 0.0)
            put(f'VOLUME{lag}', 0.0)

    log_vol = np.log(v + 1.0)
    vol_chg = np.log((v / _delay(v, 1).clip(lower=1e-12)) + 1.0)
    ret1 = c / prev.replace(0, np.nan)
    up = (c > prev).astype(float)
    down = (c < prev).astype(float)
    abs_chg = chg.abs()
    pos_chg = chg.clip(lower=0)
    neg_chg = (-chg).clip(lower=0)

    for window in ALPHA158_WINDOWS:
        put(f'ROC{window}', float(c.iloc[-1 - window]) / last_c_safe if n > window else 0.0)
        ma = _last_mean(c, window)
        std = _last_std(c, window)
        sl = _last_slope(c, window)
        mean_ready = len(_tail(c, window)) >= _minp(window)
        put(f'MA{window}', ma / last_c_safe)
        put(f'STD{window}', std / last_c_safe)
        put(f'BETA{window}', sl / last_c_safe)
        put(f'RSQR{window}', _last_rsquare(c, window))
        if mean_ready:
            put(f'RESI{window}', (last_c - (sl * (n - 1) + ma)) / last_c_safe)
        else:
            put(f'RESI{window}', 0.0)
        hi = _last_minmax(h, window, 'max')
        lo = _last_minmax(low, window, 'min')
        put(f'MAX{window}', hi / last_c_safe)
        put(f'MIN{window}', lo / last_c_safe)
        put(f'QTLU{window}', _last_quantile(c, window, 0.8) / last_c_safe)
        put(f'QTLD{window}', _last_quantile(c, window, 0.2) / last_c_safe)
        put(f'RANK{window}', _last_rank(c, window))
        put(f'RSV{window}', (last_c - lo) / (hi - lo + 1e-12))
        imax = _last_arg(h, window, 'max')
        imin = _last_arg(low, window, 'min')
        put(f'IMAX{window}', imax / float(window))
        put(f'IMIN{window}', imin / float(window))
        put(f'IMXD{window}', (imax - imin) / float(window))
        put(f'CORR{window}', _last_corr(c, log_vol, window))
        put(f'CORD{window}', _last_corr(ret1, vol_chg, window))
        cntp = _last_mean(up, window)
        cntn = _last_mean(down, window)
        put(f'CNTP{window}', cntp)
        put(f'CNTN{window}', cntn)
        put(f'CNTD{window}', cntp - cntn)
        put(f'SUM{window}', _last_sum(c, window) / last_c_safe)
        sum_abs = _last_sum(abs_chg, window)
        sump = _last_sum(pos_chg, window) / (sum_abs + 1e-12)
        sumn = _last_sum(neg_chg, window) / (sum_abs + 1e-12)
        put(f'SUMP{window}', sump)
        put(f'SUMN{window}', sumn)
        put(f'SUMD{window}', sump - sumn)

    return {k: _finite(v) for k, v in out.items()}


def compute_advanced_factors(df: pd.DataFrame) -> dict[str, Any]:
    """
    统一出口：兼容旧字段 alpha006/012/054 + qlib_sharpe20，并给出完整 101/158。
    """
    frame = _prep(df)
    if frame is None:
        return {
            'version': ALPHA_ENGINE_VERSION,
            'alpha101': {},
            'alpha158': {},
            'alpha101Count': 0,
            'alpha158Count': 0,
        }

    try:
        alpha101 = compute_alpha101(frame)
    except Exception:
        alpha101 = {}
    try:
        alpha158 = compute_alpha158(frame)
    except Exception:
        alpha158 = {}
    returns = frame['returns']
    ret20 = _last(_ts_mean(returns, 20))
    vol20 = _last(_ts_std(returns, 20))
    flat = {
        **alpha101,
        **{f'qlib_{k}': v for k, v in list(alpha158.items())[:12]},
        'qlib_sharpe20': round(ret20 / (vol20 + 1e-6), 4),
        'qlib_vol_spread': round(vol20 * math.sqrt(252), 4),
    }
    return {
        'version': ALPHA_ENGINE_VERSION,
        'alpha101': alpha101,
        'alpha158': alpha158,
        'alpha101Count': len(alpha101),
        'alpha158Count': len(alpha158),
        **flat,
    }


def alpha_schema() -> dict[str, Any]:
    return {
        'version': ALPHA_ENGINE_VERSION,
        'alpha101': {
            'key': 'alpha101',
            'label': 'WorldQuant Alpha101',
            'desc': '经典 Alpha101 时序实现（截面 rank 退化为滚动分位），覆盖动量、量价相关、日内形态等',
            'inputs': [
                'alpha001', 'alpha006', 'alpha012', 'alpha018', 'alpha023',
                'alpha041', 'alpha054', 'alpha101',
            ],
        },
        'alpha158': {
            'key': 'alpha158',
            'label': 'Qlib Alpha158',
            'desc': 'K 线形态 + OPEN/HIGH/LOW/VWAP/VOLUME 相对收盘 + 5/10/20/30/60 滚动算子（ROC/MA/STD/BETA/CORR/RSV 等）',
            'inputs': ['KMID', 'KLEN', 'ROC5', 'MA20', 'STD20', 'CORR20', 'RSV20', 'SUMD20'],
        },
        'alpha101Cs': {
            'key': 'alpha101Cs',
            'label': 'Alpha101 截面 rank',
            'desc': '对当日全市场因子值做百分位 rank，还原原文截面 rank() 口径',
            'inputs': [
                'csMom20',
                'csVolRatio20',
                'csRsi14',
                'csBreakout',
                'csAlpha001',
                'csAlpha006',
                'csAlpha012',
                'csAlpha023',
                'csAlpha041',
                'csAlpha101',
            ],
        },
    }


def _pct_rank(values: dict[str, float]) -> dict[str, float]:
    items = [(k, v) for k, v in values.items() if v is not None and not math.isnan(float(v))]
    if len(items) < 3:
        return {}
    items.sort(key=lambda x: x[1])
    n = len(items)
    out: dict[str, float] = {}
    for i, (key, _val) in enumerate(items):
        out[key] = round((i + 1) / n, 4)
    return out


def _src_value(row: dict[str, Any], src: str) -> float:
    alpha = row.get('alpha101')
    if isinstance(alpha, dict) and src in alpha:
        nested = alpha.get(src)
        if not isinstance(nested, dict):
            return _finite(nested, float('nan'))
    value = row.get(src)
    if src in row and value is not None and not isinstance(value, dict):
        return _finite(value, float('nan'))
    return float('nan')


def attach_cross_section_alphas(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    对已算好的单标的指标做截面百分位，得到 Alpha101 风格的 rank 因子。

    rows 需含 symbol，以及 return20 / rsi14 / volumeRatio20 / distanceHigh20 / alpha101 子字典。
    """
    if len(rows) < 3:
        return rows
    fields = {
        'csMom20': 'return20',
        'csRsi14': 'rsi14',
        'csVolRatio20': 'volumeRatio20',
        'csBreakout': 'distanceHigh20',
        'csAlpha001': 'alpha001',
        'csAlpha006': 'alpha006',
        'csAlpha012': 'alpha012',
        'csAlpha023': 'alpha023',
        'csAlpha041': 'alpha041',
        'csAlpha101': 'alpha101',
    }
    ranked: dict[str, dict[str, float]] = {}
    for cs_key, src in fields.items():
        ranked[cs_key] = _pct_rank({str(r.get('symbol')): _src_value(r, src) for r in rows})
    for row in rows:
        symbol = str(row.get('symbol') or '')
        cs: dict[str, float] = {}
        for cs_key in fields:
            if symbol in ranked[cs_key]:
                cs[cs_key] = ranked[cs_key][symbol]
        row['alphaCs'] = cs
        row['alphaCsCount'] = len(cs)
    return rows
