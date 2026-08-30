"""
量化因子引擎（纯函数计算，无外部基础设施依赖）。

移植自 longbridge-platform-core 的 QuantTradingService 因子体系，精简为
pandas + pandas_ta 实现。输入日K线，输出 8 大因子族的因子值 + 综合打分。

因子族（中文label）：
    趋势因子 / 价型因子 / 动量因子 / 突破因子 / 量能资金因子 / 回归因子 / 波动因子 / 流动性因子
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from module_quant.service.alpha_engine import alpha_schema, compute_advanced_factors

try:
    import pandas_ta as ta  # noqa: F401

    _HAS_PANDAS_TA = True
except Exception:  # pragma: no cover - 依赖缺失时退化为手工实现
    _HAS_PANDAS_TA = False


# ------------------------------------------------------------------ 因子族定义 ---

FACTOR_SCHEMA: list[dict[str, Any]] = [
    {
        'key': 'trend',
        'label': '趋势因子',
        'inputs': ['ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120', 'ema12', 'ema26',
                   'return20', 'return60', 'maSlope20', 'maSpread20_60', 'adx14', 'macdHist'],
        'desc': '均线多空排列、动量斜率、ADX/MACD 趋势确认',
    },
    {
        'key': 'priceAction',
        'label': '价型因子',
        'inputs': ['kMid', 'upperShadow', 'lowerShadow', 'pricePosition20', 'pricePosition60',
                   'bollPercentB20', 'vwapDistance20'],
        'desc': 'K线实体/影线形态、区间位置、布林%B、VWAP 偏离',
    },
    {
        'key': 'momentum',
        'label': '动量因子',
        'inputs': ['rsi6', 'rsi14', 'rsi28', 'roc12', 'stochK14', 'williamsR14', 'cci20'],
        'desc': 'RSI/ROC/KDJ/威廉/CCI 等动量指标',
    },
    {
        'key': 'breakout',
        'label': '突破因子',
        'inputs': ['distanceHigh20', 'distanceHigh60', 'volumeRatio20', 'volumeRatio60',
                   'dayChangePercent', 'bollBandwidth20'],
        'desc': '距区间高点距离、放量突破、布林收口',
    },
    {
        'key': 'volumeFlow',
        'label': '量能资金因子',
        'inputs': ['volumeRatio5', 'volumeRatio20', 'obvSlope20', 'mfi14', 'cmf20', 'closeVolumeCorr20'],
        'desc': 'OBV/MFI/CMF 资金流向、量价相关性',
    },
    {
        'key': 'reversion',
        'label': '回归因子',
        'inputs': ['rsi14', 'stochK14', 'bollPercentB20', 'supportDistance', 'distanceLow20', 'return20'],
        'desc': '超卖回升、支撑反弹、布林下轨回归',
    },
    {
        'key': 'volatility',
        'label': '波动因子',
        'inputs': ['volatility5', 'volatility20', 'volatility60', 'atr14Percent',
                   'bollBandwidth20', 'downsideVol20'],
        'desc': '收益波动率、ATR%、下行波动',
    },
    {
        'key': 'liquidity',
        'label': '流动性因子',
        'inputs': ['avgVolume20', 'avgDollarVolume20', 'volumeTrend20', 'vwapDistance20'],
        'desc': '成交量/成交额、量能趋势、VWAP 偏离',
    },
]

FACTOR_SCHEMA_VERSION = 'quant-factor-v2'
FACTOR_SCORE_WORKERS = 8

# 策略档位 -> 因子族权重（含综合分基线偏移）
PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    'conservative': {
        'trend': 0.24, 'priceAction': 0.14, 'momentum': 0.10, 'breakout': 0.06,
        'volumeFlow': 0.10, 'reversion': 0.20, 'volatility': 0.16, 'liquidity': 0.10,
    },
    'balanced': {
        'trend': 0.30, 'priceAction': 0.14, 'momentum': 0.18, 'breakout': 0.16,
        'volumeFlow': 0.12, 'reversion': 0.08, 'volatility': 0.10, 'liquidity': 0.06,
    },
    'aggressive': {
        'trend': 0.34, 'priceAction': 0.12, 'momentum': 0.26, 'breakout': 0.28,
        'volumeFlow': 0.16, 'reversion': 0.02, 'volatility': 0.06, 'liquidity': 0.05,
    },
}
# 风险扣分放大系数：保守型对风险更敏感
PROFILE_RISK_MULTIPLIER = {'conservative': 1.4, 'balanced': 1.0, 'aggressive': 0.7}

WEIGHT_ALIASES = {
    'volume': 'volumeFlow',
    'volume_flow': 'volumeFlow',
    'price_action': 'priceAction',
    'priceaction': 'priceAction',
    'value': 'reversion',
    'quality': 'liquidity',
}


def merge_profile_weights(profile: str, custom: dict[str, Any] | None = None) -> dict[str, float]:
    """把落库的策略权重合并进 8 大因子族默认权重。"""
    key = profile if profile in PROFILE_WEIGHTS else 'balanced'
    weights = dict(PROFILE_WEIGHTS[key])
    if not custom:
        return weights
    raw = custom.get('weights') if isinstance(custom.get('weights'), dict) else custom
    if not isinstance(raw, dict):
        return weights
    for name, value in raw.items():
        mapped = WEIGHT_ALIASES.get(str(name), str(name))
        if mapped not in weights:
            continue
        try:
            weights[mapped] = float(value)
        except (TypeError, ValueError):
            continue
    return weights


# ---------------------------------------------------------------------- 工具函数 ---


def _finite(value: Any, default: float = 0.0) -> float:
    """把任意值转成有限浮点，NaN/inf/异常统一回退默认值。"""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _ratio(numerator: float, denominator: float) -> float:
    """安全比值：分母为 0 返回 0。"""
    if not denominator:
        return 0.0
    return numerator / denominator


def klines_to_frame(klines: list[dict[str, Any]]) -> pd.DataFrame:
    """
    把 InfluxUtil.query_klines 的输出转成 DataFrame。

    :param klines: [{date, open, high, low, close, volume}, ...]（时间升序）
    :return: 数值列为 float 的 DataFrame
    """
    if not klines:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    df = pd.DataFrame(klines)
    for col in ('open', 'high', 'low', 'close', 'volume'):
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    if 'date' in df.columns:
        df = df.sort_values('date').reset_index(drop=True)
    return df


# ------------------------------------------------------------------ 指标计算 ---


def _finite_s(series: pd.Series, default: float = 0.0) -> pd.Series:
    """把序列里的非几何值换成 default，保持与 _finite 相同口径。"""
    numeric = pd.to_numeric(series, errors='coerce')
    return numeric.where(np.isfinite(numeric), default)


def _div_s(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """逐元素安全除：分母为 0 / NaN 时得 0。"""
    return numerator / denominator.replace(0, np.nan)


def _rsi_series(close: pd.Series, length: int) -> pd.Series:
    if _HAS_PANDAS_TA:
        series = ta.rsi(close, length=length)
        if series is not None:
            return _finite_s(series, 50.0)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rsi = 100 - 100 / (1 + _div_s(gain, loss))
    return _finite_s(rsi.where(loss != 0, 100.0), 50.0)


def _atr_series(df: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = df['close'].shift(1)
    tr = pd.concat(
        [
            (df['high'] - df['low']),
            (df['high'] - prev_close).abs(),
            (df['low'] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return _finite_s(tr.rolling(length).mean())


def _adx_series(df: pd.DataFrame, length: int = 14) -> pd.Series:
    zeros = pd.Series(0.0, index=df.index)
    if not _HAS_PANDAS_TA:
        return zeros
    try:
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=length)
        if adx_df is None:
            return zeros
        col = f'ADX_{length}'
        if col not in adx_df.columns:
            return zeros
        return _finite_s(adx_df[col].ffill())
    except Exception:
        return zeros


def _obv_slope_series(close: pd.Series, volume: pd.Series, length: int = 20) -> pd.Series:
    direction = np.sign(close.diff().fillna(0.0))
    obv = (direction * volume).cumsum()
    past = obv.shift(length - 1)
    base = past.abs()
    base = base.where(base != 0, obv.abs()).replace(0, 1.0)
    slope = _div_s(obv - past, base) * 100
    ready = pd.Series(np.arange(len(close), dtype=np.int64), index=close.index) >= length
    return _finite_s(slope.where(ready, 0.0))


def _mfi_series(df: pd.DataFrame, length: int = 14) -> pd.Series:
    typical = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical * df['volume']
    delta = typical.diff()
    pos = money_flow.where(delta > 0, 0.0).rolling(length).sum()
    neg = money_flow.where(delta < 0, 0.0).rolling(length).sum()
    mfi = 100 - 100 / (1 + _div_s(pos, neg))
    return _finite_s(mfi.where(neg != 0, 100.0))


def _cmf_series(df: pd.DataFrame, length: int = 20) -> pd.Series:
    high, low, close, volume = df['high'], df['low'], df['close'], df['volume']
    hl = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / hl
    mfv = (mfm * volume).fillna(0.0)
    denom = volume.rolling(length).sum()
    return _finite_s(_div_s(mfv.rolling(length).sum(), denom))


def _cci_series(df: pd.DataFrame, length: int = 20) -> pd.Series:
    typical = (df['high'] + df['low'] + df['close']) / 3
    sma = typical.rolling(length).mean()
    mad = typical.rolling(length).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return _finite_s(_div_s(typical - sma, 0.015 * mad))


def _cci_last(df: pd.DataFrame, length: int = 20) -> float:
    typical = (df['high'] + df['low'] + df['close']) / 3
    if len(typical) < length:
        return 0.0
    chunk = typical.iloc[-length:]
    sma = float(chunk.mean())
    mad = float(np.abs(chunk.to_numpy(dtype=float) - sma).mean())
    return _finite(_ratio(float(typical.iloc[-1]) - sma, 0.015 * mad))


def _downside_vol_last(close: pd.Series, length: int) -> float:
    if len(close) < length:
        return 0.0
    window = close.pct_change().iloc[-length:].to_numpy(dtype=float)
    negative = window[np.isfinite(window) & (window < 0)]
    if len(negative) < 2:
        return 0.0
    return _finite(float(np.std(negative, ddof=1) * 100))


def _max_drawdown_last(close: pd.Series, length: int) -> float:
    if len(close) < length:
        return 0.0
    window = close.iloc[-length:].to_numpy(dtype=float)
    if window.size == 0:
        return 0.0
    peak = np.maximum.accumulate(window)
    peak = np.where(peak == 0, np.nan, peak)
    return _finite(float(np.nanmin((window - peak) / peak) * 100))


def _macd_hist_series(close: pd.Series) -> pd.Series:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    return _finite_s(dif - dea)


def _period_return_series(close: pd.Series, period: int) -> pd.Series:
    return _finite_s(close.pct_change(period) * 100)


def _volatility_series(close: pd.Series, length: int) -> pd.Series:
    return _finite_s(close.pct_change().rolling(length).std() * 100)


def _downside_vol_series(close: pd.Series, length: int) -> pd.Series:
    returns = close.pct_change()

    def _std_neg(window: np.ndarray) -> float:
        negative = window[np.isfinite(window) & (window < 0)]
        if len(negative) < 2:
            return 0.0
        return float(np.std(negative, ddof=1) * 100)

    return _finite_s(returns.rolling(length).apply(_std_neg, raw=True))


def _max_drawdown_series(close: pd.Series, length: int) -> pd.Series:
    def _window_dd(window: np.ndarray) -> float:
        if window.size == 0:
            return 0.0
        peak = np.maximum.accumulate(window)
        peak = np.where(peak == 0, np.nan, peak)
        return float(np.nanmin((window - peak) / peak) * 100)

    return _finite_s(close.rolling(length).apply(_window_dd, raw=True))


def _empty_alpha() -> dict[str, Any]:
    return {'alpha101': {}, 'alpha158': {}, 'alpha101Count': 0, 'alpha158Count': 0}


# ------------------------------------------------------------------ 指标快照 ---


def _roll_last(series: pd.Series, length: int, how: str) -> float:
    if length <= 0 or len(series) < length:
        return 0.0
    chunk = series.iloc[-length:]
    if how == 'mean':
        return _finite(chunk.mean())
    if how == 'std':
        return _finite(chunk.std())
    if how == 'sum':
        return _finite(chunk.sum())
    if how == 'max':
        return _finite(chunk.max())
    if how == 'min':
        return _finite(chunk.min())
    return 0.0


def _series_last(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default
    return _finite(series.iloc[-1], default)


def _compute_family_last_row(df: pd.DataFrame) -> pd.DataFrame:
    """只算末根 8 族，口径对齐 compute_family_frame 最后一行。"""
    close, high, low, volume = df['close'], df['high'], df['low'], df['volume']
    n = len(df)
    last_close = _finite(close.iloc[-1])
    last_open = _finite(df['open'].iloc[-1])
    last_high = _finite(high.iloc[-1])
    last_low = _finite(low.iloc[-1])
    last_volume = _finite(volume.iloc[-1])
    prev_close = _finite(close.iloc[-2]) if n >= 2 else 0.0

    ma5 = _roll_last(close, 5, 'mean')
    ma10 = _roll_last(close, 10, 'mean')
    ma20 = _roll_last(close, 20, 'mean')
    ma25 = _roll_last(close, 25, 'mean')
    ma30 = _roll_last(close, 30, 'mean')
    ma60 = _roll_last(close, 60, 'mean')
    ma120 = _roll_last(close, 120, 'mean')
    ema12 = _series_last(_finite_s(close.ewm(span=12, adjust=False).mean()))
    ema26 = _series_last(_finite_s(close.ewm(span=26, adjust=False).mean()))

    boll_mid = ma20
    boll_std = _roll_last(close, 20, 'std')
    boll_upper = boll_mid + 2 * boll_std
    boll_lower = boll_mid - 2 * boll_std
    boll_span = boll_upper - boll_lower
    boll_bandwidth = _finite(_ratio(boll_span, boll_mid) * 100)
    boll_percent_b = 50.0 if boll_span == 0 else _finite(_ratio(last_close - boll_lower, boll_span) * 100, 50.0)

    high20 = _roll_last(high, 20, 'max')
    low20 = _roll_last(low, 20, 'min')
    high60 = _roll_last(high, 60, 'max') if n >= 60 else high20
    low60 = _roll_last(low, 60, 'min') if n >= 60 else low20
    price_position20 = 50.0 if high20 == low20 else _finite(_ratio(last_close - low20, high20 - low20) * 100, 50.0)
    price_position60 = 50.0 if high60 == low60 else _finite(_ratio(last_close - low60, high60 - low60) * 100, 50.0)
    distance_high20 = _finite(_ratio(last_close - high20, high20) * 100)
    distance_high60 = _finite(_ratio(last_close - high60, high60) * 100)
    distance_low20 = _finite(_ratio(last_close - low20, low20) * 100)

    avg_volume5 = _roll_last(volume, 5, 'mean')
    avg_volume20 = _roll_last(volume, 20, 'mean')
    avg_volume60 = _roll_last(volume, 60, 'mean') if n >= 60 else avg_volume20
    volume_ratio5 = _finite(_ratio(last_volume, avg_volume5))
    volume_ratio20 = _finite(_ratio(last_volume, avg_volume20))
    volume_ratio60 = _finite(_ratio(last_volume, avg_volume60))
    volume_trend20 = _finite(_ratio(avg_volume5 - avg_volume20, avg_volume20) * 100)
    avg_dollar_volume20 = _roll_last(close * volume, 20, 'mean')
    close_volume_corr20 = _finite(close.iloc[-20:].corr(volume.iloc[-20:])) if n >= 20 else 0.0

    typical = (high + low + close) / 3
    vol_sum20 = _roll_last(volume, 20, 'sum')
    if vol_sum20 == 0:
        vwap20 = last_close
    else:
        vwap20 = _finite(_ratio(_roll_last(typical * volume, 20, 'sum'), vol_sum20))
    vwap_distance20 = _finite(_ratio(last_close - vwap20, vwap20) * 100)

    atr14 = _series_last(_atr_series(df, 14))
    return20 = _finite(close.pct_change(20).iloc[-1] * 100) if n > 20 else 0.0
    return5 = _finite(close.pct_change(5).iloc[-1] * 100) if n > 5 else 0.0
    return60 = _finite(close.pct_change(60).iloc[-1] * 100) if n > 60 else 0.0
    volatility20 = _series_last(_volatility_series(close, 20))
    ma_slope20 = _finite(_ratio(ma20 - ma25, ma25) * 100) if n >= 25 else 0.0

    high14 = _roll_last(high, 14, 'max')
    low14 = _roll_last(low, 14, 'min')
    stoch_span = high14 - low14
    stoch_k = 50.0 if stoch_span == 0 else _finite(_ratio(last_close - low14, stoch_span) * 100, 50.0)
    williams_r = -50.0 if stoch_span == 0 else _finite(_ratio(high14 - last_close, stoch_span) * -100, -50.0)

    row = {
        'date': df['date'].iloc[-1] if 'date' in df.columns else None,
        'latestClose': last_close,
        'dayChangePercent': _finite(_ratio(last_close - prev_close, prev_close) * 100),
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'ma30': ma30,
        'ma60': ma60,
        'ma120': ma120,
        'ema12': ema12,
        'ema26': ema26,
        'return5': return5,
        'return20': return20,
        'return60': return60,
        'returnVolatilityRatio20': _finite(_ratio(return20, volatility20)),
        'maSlope20': ma_slope20,
        'maSpread20_60': _finite(_ratio(ma20 - ma60, ma60) * 100),
        'adx14': _series_last(_adx_series(df, 14)),
        'macdHist': _series_last(_macd_hist_series(close)),
        'kMid': _finite(_ratio(last_close - last_open, last_open) * 100),
        'upperShadow': _finite(_ratio(last_high - max(last_open, last_close), last_close) * 100),
        'lowerShadow': _finite(_ratio(min(last_open, last_close) - last_low, last_close) * 100),
        'pricePosition20': price_position20,
        'pricePosition60': price_position60,
        'bollMid20': boll_mid,
        'bollUpper20': boll_upper,
        'bollLower20': boll_lower,
        'bollBandwidth20': boll_bandwidth,
        'bollPercentB20': boll_percent_b,
        'vwap20': vwap20,
        'vwapDistance20': vwap_distance20,
        'rsi6': _series_last(_rsi_series(close, 6), 50.0),
        'rsi14': _series_last(_rsi_series(close, 14), 50.0),
        'rsi28': _series_last(_rsi_series(close, 28), 50.0),
        'roc12': _finite(close.pct_change(12).iloc[-1] * 100) if n > 12 else 0.0,
        'stochK14': stoch_k,
        'williamsR14': williams_r,
        'distanceHigh20': distance_high20,
        'distanceHigh60': distance_high60,
        'distanceLow20': distance_low20,
        'supportDistance': abs(distance_low20),
        'avgVolume5': avg_volume5,
        'avgVolume20': avg_volume20,
        'avgVolume60': avg_volume60,
        'volumeRatio5': volume_ratio5,
        'volumeRatio20': volume_ratio20,
        'volumeRatio60': volume_ratio60,
        'volumeTrend20': volume_trend20,
        'avgDollarVolume20': avg_dollar_volume20,
        'obvSlope20': _series_last(_obv_slope_series(close, volume, 20)),
        'mfi14': _series_last(_mfi_series(df, 14)),
        'cmf20': _series_last(_cmf_series(df, 20)),
        'closeVolumeCorr20': close_volume_corr20,
        'volatility5': _series_last(_volatility_series(close, 5)),
        'volatility20': volatility20,
        'volatility60': _series_last(_volatility_series(close, 60)),
        'atr14': atr14,
        'atr14Percent': _finite(_ratio(atr14, last_close) * 100),
        'downsideVol20': _downside_vol_last(close, 20),
        'maxDrawdown20': _max_drawdown_last(close, 20),
        'maxDrawdown60': _max_drawdown_last(close, 60),
        'cci20': _cci_last(df, 20),
    }
    return pd.DataFrame([row])


def compute_family_frame(
    klines: list[dict[str, Any]] | pd.DataFrame,
    last_only: bool = False,
) -> pd.DataFrame | None:
    """
    一次算出整段 8 族指标序列。第 i 行等价于只用 klines[:i+1] 取末根。
    不含 Alpha101/158（回测打分用不到）。
    last_only=True 时只返回末行，CCI/下行波动/回撤走最后窗口，避开整段 apply。
    """
    df = klines if isinstance(klines, pd.DataFrame) else klines_to_frame(klines)
    if len(df) < 20:
        return None
    if last_only:
        return _compute_family_last_row(df)

    close, high, low, volume = df['close'], df['high'], df['low'], df['volume']
    prev_close = close.shift(1)
    row_idx = pd.Series(np.arange(len(df), dtype=np.int64), index=df.index)
    ready60 = row_idx >= 59

    ma5 = _finite_s(close.rolling(5).mean())
    ma10 = _finite_s(close.rolling(10).mean())
    ma20 = _finite_s(close.rolling(20).mean())
    ma25 = _finite_s(close.rolling(25).mean())
    ma30 = _finite_s(close.rolling(30).mean())
    ma60 = _finite_s(close.rolling(60).mean())
    ma120 = _finite_s(close.rolling(120).mean())
    ema12 = _finite_s(close.ewm(span=12, adjust=False).mean())
    ema26 = _finite_s(close.ewm(span=26, adjust=False).mean())

    boll_mid = ma20
    boll_std = _finite_s(close.rolling(20).std())
    boll_upper = boll_mid + 2 * boll_std
    boll_lower = boll_mid - 2 * boll_std
    boll_bandwidth = _finite_s(_div_s(boll_upper - boll_lower, boll_mid) * 100)
    boll_span = boll_upper - boll_lower
    boll_percent_b = _finite_s(_div_s(close - boll_lower, boll_span) * 100, 50.0)
    boll_percent_b = boll_percent_b.where(boll_span != 0, 50.0)

    high20 = _finite_s(high.rolling(20).max())
    low20 = _finite_s(low.rolling(20).min())
    high60 = _finite_s(high.rolling(60).max()).where(ready60, high20)
    low60 = _finite_s(low.rolling(60).min()).where(ready60, low20)
    price_position20 = _finite_s(_div_s(close - low20, high20 - low20) * 100, 50.0)
    price_position20 = price_position20.where(high20 != low20, 50.0)
    price_position60 = _finite_s(_div_s(close - low60, high60 - low60) * 100, 50.0)
    price_position60 = price_position60.where(high60 != low60, 50.0)
    distance_high20 = _finite_s(_div_s(close - high20, high20) * 100)
    distance_high60 = _finite_s(_div_s(close - high60, high60) * 100)
    distance_low20 = _finite_s(_div_s(close - low20, low20) * 100)

    avg_volume5 = _finite_s(volume.rolling(5).mean())
    avg_volume20 = _finite_s(volume.rolling(20).mean())
    avg_volume60 = _finite_s(volume.rolling(60).mean()).where(ready60, avg_volume20)
    volume_ratio5 = _finite_s(_div_s(volume, avg_volume5))
    volume_ratio20 = _finite_s(_div_s(volume, avg_volume20))
    volume_ratio60 = _finite_s(_div_s(volume, avg_volume60))
    volume_trend20 = _finite_s(_div_s(avg_volume5 - avg_volume20, avg_volume20) * 100)
    avg_dollar_volume20 = _finite_s((close * volume).rolling(20).mean())
    close_volume_corr20 = _finite_s(close.rolling(20).corr(volume))

    typical = (high + low + close) / 3
    vol_sum20 = volume.rolling(20).sum()
    vwap20 = _finite_s(_div_s((typical * volume).rolling(20).sum(), vol_sum20))
    vwap20 = vwap20.where(vol_sum20 != 0, close)
    vwap_distance20 = _finite_s(_div_s(close - vwap20, vwap20) * 100)

    latest_open = _finite_s(df['open'])
    k_mid = _finite_s(_div_s(close - latest_open, latest_open) * 100)
    upper_shadow = _finite_s(_div_s(high - np.maximum(latest_open, close), close) * 100)
    lower_shadow = _finite_s(_div_s(np.minimum(latest_open, close) - low, close) * 100)

    atr14 = _atr_series(df, 14)
    return20 = _period_return_series(close, 20)
    volatility20 = _volatility_series(close, 20)
    ma_slope20 = _finite_s(_div_s(ma20 - ma25, ma25) * 100)
    ma_slope20 = ma_slope20.where(row_idx >= 24, 0.0)

    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    stoch_span = high14 - low14
    stoch_k = _finite_s(_div_s(close - low14, stoch_span) * 100, 50.0)
    williams_r = _finite_s(_div_s(high14 - close, stoch_span) * -100, -50.0)

    frame = pd.DataFrame(
        {
            'date': df['date'] if 'date' in df.columns else pd.Series(index=df.index, dtype=object),
            'latestClose': close,
            'dayChangePercent': _finite_s(_div_s(close - prev_close, prev_close) * 100),
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma30': ma30,
            'ma60': ma60,
            'ma120': ma120,
            'ema12': ema12,
            'ema26': ema26,
            'return5': _period_return_series(close, 5),
            'return20': return20,
            'return60': _period_return_series(close, 60),
            'returnVolatilityRatio20': _finite_s(_div_s(return20, volatility20)),
            'maSlope20': ma_slope20,
            'maSpread20_60': _finite_s(_div_s(ma20 - ma60, ma60) * 100),
            'adx14': _adx_series(df, 14),
            'macdHist': _macd_hist_series(close),
            'kMid': k_mid,
            'upperShadow': upper_shadow,
            'lowerShadow': lower_shadow,
            'pricePosition20': price_position20,
            'pricePosition60': price_position60,
            'bollMid20': boll_mid,
            'bollUpper20': boll_upper,
            'bollLower20': boll_lower,
            'bollBandwidth20': boll_bandwidth,
            'bollPercentB20': boll_percent_b,
            'vwap20': vwap20,
            'vwapDistance20': vwap_distance20,
            'rsi6': _rsi_series(close, 6),
            'rsi14': _rsi_series(close, 14),
            'rsi28': _rsi_series(close, 28),
            'roc12': _period_return_series(close, 12),
            'stochK14': stoch_k,
            'williamsR14': williams_r,
            'distanceHigh20': distance_high20,
            'distanceHigh60': distance_high60,
            'distanceLow20': distance_low20,
            'supportDistance': distance_low20.abs(),
            'avgVolume5': avg_volume5,
            'avgVolume20': avg_volume20,
            'avgVolume60': avg_volume60,
            'volumeRatio5': volume_ratio5,
            'volumeRatio20': volume_ratio20,
            'volumeRatio60': volume_ratio60,
            'volumeTrend20': volume_trend20,
            'avgDollarVolume20': avg_dollar_volume20,
            'obvSlope20': _obv_slope_series(close, volume, 20),
            'mfi14': _mfi_series(df, 14),
            'cmf20': _cmf_series(df, 20),
            'closeVolumeCorr20': close_volume_corr20,
            'volatility5': _volatility_series(close, 5),
            'volatility20': volatility20,
            'volatility60': _volatility_series(close, 60),
            'atr14': atr14,
            'atr14Percent': _finite_s(_div_s(atr14, close) * 100),
            'downsideVol20': _downside_vol_series(close, 20),
            'maxDrawdown20': _max_drawdown_series(close, 20),
            'maxDrawdown60': _max_drawdown_series(close, 60),
            'cci20': _cci_series(df, 20),
        }
    )
    return frame


_ROUND_4 = (
    'latestClose', 'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120', 'ema12', 'ema26',
    'macdHist', 'bollMid20', 'bollUpper20', 'bollLower20', 'vwap20', 'atr14', 'cmf20',
    'closeVolumeCorr20',
)
_ROUND_2 = (
    'dayChangePercent', 'return5', 'return20', 'return60', 'returnVolatilityRatio20',
    'maSlope20', 'maSpread20_60', 'adx14', 'kMid', 'upperShadow', 'lowerShadow',
    'pricePosition20', 'pricePosition60', 'bollBandwidth20', 'bollPercentB20',
    'vwapDistance20', 'rsi6', 'rsi14', 'rsi28', 'roc12', 'stochK14', 'williamsR14',
    'cci20', 'distanceHigh20', 'distanceHigh60', 'distanceLow20', 'supportDistance',
    'avgVolume5', 'avgVolume20', 'avgVolume60', 'volumeRatio5', 'volumeRatio20',
    'volumeRatio60', 'volumeTrend20', 'avgDollarVolume20', 'obvSlope20', 'mfi14',
    'volatility5', 'volatility20', 'volatility60', 'atr14Percent', 'downsideVol20',
    'maxDrawdown20', 'maxDrawdown60',
)


def _as_metric_map(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, 'to_dict'):
        return row.to_dict()
    if hasattr(row, '_asdict'):
        return row._asdict()
    return dict(row)


def metrics_from_frame_row(row: Any, history_count: int) -> dict[str, Any]:
    """把 compute_family_frame 的一行收成与 compute_metrics 相同的打分输入。"""
    if history_count < 20:
        return {'ok': False, 'reason': f'K线数据不足（{history_count}<20），无法计算因子', 'historyCount': history_count}
    data = _as_metric_map(row)
    metrics: dict[str, Any] = {
        'ok': True,
        'tradeDate': data.get('date'),
        'historyCount': history_count,
    }
    for key in _ROUND_4:
        metrics[key] = round(_finite(data.get(key)), 4)
    for key in _ROUND_2:
        metrics[key] = round(_finite(data.get(key)), 2)
    return metrics


def compute_metrics(klines: list[dict[str, Any]], include_alpha: bool = True) -> dict[str, Any]:
    """
    根据历史K线计算全量因子指标快照。

    :param klines: [{date, open, high, low, close, volume}, ...] 时间升序，建议 >=60 根
    :param include_alpha: 是否附带 Alpha101/158；回测打分可关
    :return: 指标字典（各因子族的原始因子值），数据不足时返回 {'ok': False, ...}
    """
    df = klines_to_frame(klines)
    frame = compute_family_frame(df, last_only=True)
    if frame is None:
        return {'ok': False, 'reason': f'K线数据不足（{len(df)}<20），无法计算因子', 'historyCount': len(df)}
    metrics = metrics_from_frame_row(frame.iloc[-1], len(df))
    advanced = compute_alpha_factors(df) if include_alpha else _empty_alpha()
    metrics['alphaFactors'] = advanced
    metrics['alpha101'] = advanced.get('alpha101') or {}
    metrics['alpha158'] = advanced.get('alpha158') or {}
    metrics['alpha101Count'] = advanced.get('alpha101Count') or 0
    metrics['alpha158Count'] = advanced.get('alpha158Count') or 0
    return metrics


# ------------------------------------------------------------------ 打分 ---


def score_metrics(
    metrics: dict[str, Any],
    strategy_profile: str = 'balanced',
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    对指标快照按 8 大因子族打分，返回各族得分 + 综合分 + 风险等级 + 标签。

    :param metrics: compute_metrics 的输出
    :param strategy_profile: conservative / balanced / aggressive
    :return: {total, trend, priceAction, ..., riskLevel, trendDirection, tags}
    """
    profile = strategy_profile if strategy_profile in PROFILE_WEIGHTS else 'balanced'
    g = lambda k, d=0.0: _finite(metrics.get(k), d)  # noqa: E731

    latest_close = g('latestClose')
    ma5, ma10, ma20, ma30, ma60, ma120 = g('ma5'), g('ma10'), g('ma20'), g('ma30'), g('ma60'), g('ma120')
    ema12, ema26 = g('ema12'), g('ema26')
    rsi6, rsi14, rsi28 = g('rsi6', 50.0), g('rsi14', 50.0), g('rsi28', 50.0)
    tags: list[str] = []

    # --- 趋势因子 ---
    trend = 0.0
    if latest_close and ma20 and latest_close >= ma20:
        trend += 11
        tags.append('站上20日线')
    if ma5 and ma10 and ma5 >= ma10:
        trend += 4
    if ma20 and ma60 and ma20 >= ma60:
        trend += 10
        tags.append('20/60多头')
    if ma60 and ma120 and ma60 >= ma120:
        trend += 6
        tags.append('中期趋势顺')
    if ma20 and ma30 and ma20 >= ma30:
        trend += 3
    if ema12 and ema26 and ema12 >= ema26:
        trend += 5
    trend += max(-8, min(10, g('return20') / 1.8))
    trend += max(-6, min(8, g('return60') / 3.5))
    trend += max(-5, min(6, g('maSlope20') / 1.8))
    trend += max(-4, min(6, g('maSpread20_60') / 2.2))
    if g('adx14') >= 25:
        trend += 5
        tags.append('ADX趋势确认')
    if g('macdHist') > 0:
        trend += 4
        tags.append('MACD偏多')

    # --- 价型因子 ---
    price_action = 0.0
    pp20, pp60 = g('pricePosition20', 50.0), g('pricePosition60', 50.0)
    k_mid = g('kMid')
    if 55 <= pp20 <= 92:
        price_action += 7
    elif pp20 >= 92:
        price_action += 3
    elif pp20 <= 18:
        price_action -= 5
    if 50 <= pp60 <= 90:
        price_action += 5
    if k_mid > 0:
        price_action += min(5, k_mid * 1.2)
    if g('lowerShadow') >= g('upperShadow') * 1.4 and k_mid >= -1.0:
        price_action += 4
        tags.append('下影承接')
    if g('upperShadow') >= 3.0 and k_mid < 0:
        price_action -= 5
    boll_b = g('bollPercentB20', 50.0)
    if 45 <= boll_b <= 88:
        price_action += 4
    elif boll_b > 115:
        price_action -= 4
    price_action += max(-4, min(4, g('vwapDistance20') / 2.5))

    # --- 动量因子 ---
    momentum = 0.0
    momentum += max(-7, min(8, g('roc12') / 2.0))
    momentum += max(-6, min(8, g('returnVolatilityRatio20') * 2.0))
    if 52 <= rsi14 <= 72:
        momentum += 7
        tags.append('RSI强势区')
    elif rsi14 > 78:
        momentum -= 6
    elif rsi14 < 35:
        momentum -= 4
    if rsi6 >= rsi14 >= rsi28 and rsi14 >= 50:
        momentum += 5
    stoch = g('stochK14', 50.0)
    if 45 <= stoch <= 82:
        momentum += 4
    elif stoch > 92:
        momentum -= 4
    wr = g('williamsR14', -50.0)
    if -65 <= wr <= -20:
        momentum += 3
    elif wr > -10:
        momentum -= 3
    cci = g('cci20')
    if 0 <= cci <= 180:
        momentum += 4
    elif cci > 240 or cci < -180:
        momentum -= 4

    # --- 突破因子 ---
    breakout = 0.0
    dh20, dh60 = g('distanceHigh20'), g('distanceHigh60')
    vr20 = g('volumeRatio20')
    if dh20 >= 0:
        breakout += 11
        tags.append('20日突破')
    elif dh20 >= -2.0:
        breakout += 7
        tags.append('接近20日高点')
    if dh60 >= 0:
        breakout += 8
        tags.append('60日突破')
    elif dh60 >= -3.5:
        breakout += 4
    if vr20 >= 1.5:
        breakout += 7
        tags.append('明显放量')
    elif vr20 >= 1.15:
        breakout += 4
        tags.append('温和放量')
    if g('volumeRatio60') >= 1.2:
        breakout += 3
    if g('return20') > 0 and g('dayChangePercent') > 0:
        breakout += 4
    if g('bollBandwidth20') <= 8 and dh20 >= -4:
        breakout += 3

    # --- 量能资金因子 ---
    volume_flow = 0.0
    if g('volumeRatio5') >= 1.1 and g('dayChangePercent') > 0:
        volume_flow += 5
    if g('obvSlope20') > 0:
        volume_flow += min(7, g('obvSlope20') / 4)
        tags.append('OBV走强')
    mfi = g('mfi14', 50.0)
    if 45 <= mfi <= 75:
        volume_flow += 5
    elif mfi > 85:
        volume_flow -= 4
    elif mfi < 25:
        volume_flow -= 3
    cmf = g('cmf20')
    if cmf > 0.05:
        volume_flow += 5
        tags.append('资金流入')
    elif cmf < -0.08:
        volume_flow -= 5
    volume_flow += max(-4, min(4, g('closeVolumeCorr20') * 5))

    # --- 回归因子 ---
    reversion = 0.0
    support = g('supportDistance', 100.0)
    if 28 <= rsi14 <= 45 and support <= 4.0:
        reversion += 10
        tags.append('支撑回升')
    if rsi14 < 35 and g('dayChangePercent') > 0:
        reversion += 7
        tags.append('RSI低位反弹')
    if latest_close and ma20 and latest_close < ma20 and g('return20') > -8:
        reversion += 4
    if g('bollPercentB20', 50.0) <= 18 and g('dayChangePercent') > 0:
        reversion += 6
        tags.append('布林下轨反弹')
    if g('distanceLow20') <= 4 and g('return5') > 0:
        reversion += 4

    # --- 波动因子 ---
    volatility = 0.0
    vol20 = g('volatility20')
    atr_pct = g('atr14Percent')
    bandwidth = g('bollBandwidth20')
    if 0.8 <= vol20 <= 3.4:
        volatility += 7
    elif vol20 < 0.8 and g('return20') > 0:
        volatility += 2
    elif vol20 >= 5.2:
        volatility -= 8
    if 0.4 <= atr_pct <= 4.0:
        volatility += 5
    elif atr_pct > 6.0:
        volatility -= 7
    if 4 <= bandwidth <= 18:
        volatility += 4
    elif bandwidth > 30:
        volatility -= 4
    volatility -= max(0, min(6, (g('downsideVol20') - 2.5) * 1.5))

    # --- 流动性因子 ---
    liquidity = 0.0
    adv20 = g('avgDollarVolume20')
    av20 = g('avgVolume20')
    if adv20 >= 50_000_000:
        liquidity += 8
    elif adv20 >= 5_000_000:
        liquidity += 5
    elif av20 > 0:
        liquidity += 2
    if g('volumeTrend20') > 0:
        liquidity += min(4, g('volumeTrend20') / 12)
    if abs(g('vwapDistance20')) <= 5:
        liquidity += 3

    # --- 风险扣分 ---
    risk_penalty = 0.0
    risk_level = 'low'
    if vol20 >= 5.2 or atr_pct >= 6.0:
        risk_penalty += 14
        risk_level = 'high'
    elif vol20 >= 3.4 or atr_pct >= 4.0:
        risk_penalty += 6
        risk_level = 'medium'
    if rsi14 >= 82:
        risk_penalty += 9
        risk_level = 'medium' if risk_level == 'low' else risk_level
    if g('return20') <= -12 or dh20 <= -18:
        risk_penalty += 12
        risk_level = 'high'
    if g('maxDrawdown20') <= -14 or g('maxDrawdown60') <= -22:
        risk_penalty += 9
        risk_level = 'high'
    if g('downsideVol20') >= 4.5:
        risk_penalty += 6
        risk_level = 'medium' if risk_level == 'low' else risk_level
    risk_penalty *= PROFILE_RISK_MULTIPLIER.get(profile, 1.0)

    weights = merge_profile_weights(profile, weights)
    raw_total = (
        42
        + trend * weights['trend']
        + price_action * weights['priceAction']
        + momentum * weights['momentum']
        + breakout * weights['breakout']
        + volume_flow * weights['volumeFlow']
        + reversion * weights['reversion']
        + volatility * weights['volatility']
        + liquidity * weights['liquidity']
        - risk_penalty
    )
    total = round(max(0.0, min(100.0, raw_total)), 2)
    trend_direction = 'up' if trend + momentum * 0.35 >= 22 else 'down' if trend <= -5 else 'sideways'

    return {
        'factorVersion': FACTOR_SCHEMA_VERSION,
        'strategyProfile': profile,
        'total': total,
        'trend': round(trend, 2),
        'priceAction': round(price_action, 2),
        'momentum': round(momentum, 2),
        'breakout': round(breakout, 2),
        'volumeFlow': round(volume_flow, 2),
        'reversion': round(reversion, 2),
        'volatility': round(volatility, 2),
        'liquidity': round(liquidity, 2),
        'riskPenalty': round(risk_penalty, 2),
        'riskLevel': risk_level,
        'trendDirection': trend_direction,
        'tags': tags or ['持续观察'],
    }


def compute_alpha_factors(df: pd.DataFrame) -> dict[str, Any]:
    """
    计算 WorldQuant Alpha101 及 Qlib Alpha158 高阶因子（末根 K 线取值）。
    """
    return compute_advanced_factors(df)


class FactorService:
    """
    因子引擎服务：整合 K线拉取 -> 指标计算 -> 打分。
    """

    @classmethod
    def get_factor_schema(cls) -> dict[str, Any]:
        """返回 8 大因子族体系定义（供前端展示）。"""
        advanced = alpha_schema()
        families = list(FACTOR_SCHEMA) + [advanced['alpha101'], advanced['alpha158'], advanced['alpha101Cs']]
        return {
            'version': FACTOR_SCHEMA_VERSION,
            'familyCount': len(families),
            'profiles': list(PROFILE_WEIGHTS.keys()),
            'families': families,
            'alphaEngine': advanced['version'],
        }

    @classmethod
    def compute_from_klines(
        cls,
        klines: list[dict[str, Any]],
        strategy_profile: str = 'balanced',
        weights: dict[str, float] | None = None,
        include_alpha: bool = True,
    ) -> dict[str, Any]:
        """
        对给定K线计算因子 + 打分（纯计算，不访问数据库/行情源）。

        :return: {'ok': bool, 'metrics': {...}, 'score': {...}} 或错误信息
        """
        metrics = compute_metrics(klines, include_alpha=include_alpha)
        if not metrics.get('ok'):
            return {'ok': False, 'reason': metrics.get('reason'), 'historyCount': metrics.get('historyCount', 0)}
        score = score_metrics(metrics, strategy_profile, weights=weights)
        return {'ok': True, 'metrics': metrics, 'score': score}

    @classmethod
    def compute_score_series(
        cls,
        klines: list[dict[str, Any]],
        strategy_profile: str = 'balanced',
        weights: dict[str, float] | None = None,
    ) -> list[dict[str, Any] | None]:
        """
        一次算完整 8 族序列，逐日打分。第 i 项对应截至当日的 score，不足 20 根为 None。
        不含 Alpha。
        """
        frame = compute_family_frame(klines)
        if frame is None:
            return [None] * len(klines)
        out: list[dict[str, Any] | None] = []
        for history_count, row in enumerate(frame.itertuples(index=False), start=1):
            as_dict = row._asdict() if hasattr(row, '_asdict') else dict(row)
            metrics = metrics_from_frame_row(as_dict, history_count)
            if not metrics.get('ok'):
                out.append(None)
                continue
            out.append(score_metrics(metrics, strategy_profile, weights=weights))
        if len(out) < len(klines):
            out.extend([None] * (len(klines) - len(out)))
        return out[: len(klines)]

    @classmethod
    def compute_symbol(
        cls,
        symbol: str,
        market: str = 'US',
        strategy_profile: str = 'balanced',
        start: str = '-1y',
        weights: dict[str, float] | None = None,
        include_alpha: bool = True,
    ) -> dict[str, Any]:
        """
        拉取时序库K线并计算某标的因子 + 打分。

        :param symbol: 标的代码
        :param market: 市场（US/HK/CN），决定时序库bucket
        :param strategy_profile: 策略档位
        :param start: Flux 起始时间
        """
        from utils.influx_util import InfluxUtil

        try:
            klines = InfluxUtil.query_klines(market, symbol, start=start, limit=320)
        except Exception as exc:  # 时序库不可用时不崩溃
            return {'ok': False, 'symbol': symbol, 'market': market, 'reason': f'K线拉取失败: {exc}'}
        result = cls.compute_from_klines(klines, strategy_profile, weights=weights, include_alpha=include_alpha)
        result['symbol'] = symbol
        result['market'] = market
        return result
