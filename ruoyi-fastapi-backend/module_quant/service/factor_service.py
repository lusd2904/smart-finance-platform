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

FACTOR_SCHEMA_VERSION = 'quant-factor-v1'

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


def _rsi(close: pd.Series, length: int) -> float:
    if _HAS_PANDAS_TA:
        series = ta.rsi(close, length=length)
        if series is not None and len(series.dropna()):
            return _finite(series.dropna().iloc[-1], 50.0)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = _ratio(_finite(gain.iloc[-1]), _finite(loss.iloc[-1]))
    return 100 - 100 / (1 + rs) if loss.iloc[-1] else 100.0


def _atr(df: pd.DataFrame, length: int = 14) -> float:
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return _finite(tr.rolling(length).mean().iloc[-1])


def _adx(df: pd.DataFrame, length: int = 14) -> float:
    if _HAS_PANDAS_TA:
        try:
            adx_df = ta.adx(df['high'], df['low'], df['close'], length=length)
            if adx_df is not None:
                col = f'ADX_{length}'
                if col in adx_df.columns and len(adx_df[col].dropna()):
                    return _finite(adx_df[col].dropna().iloc[-1])
        except Exception:
            pass
    return 0.0


def _obv_slope(df: pd.DataFrame, length: int = 20) -> float:
    close, volume = df['close'], df['volume']
    direction = np.sign(close.diff().fillna(0.0))
    obv = (direction * volume).cumsum()
    if len(obv) <= length:
        return 0.0
    recent, past = _finite(obv.iloc[-1]), _finite(obv.iloc[-length])
    base = abs(past) if past else (abs(recent) or 1.0)
    return _ratio(recent - past, base) * 100


def _mfi(df: pd.DataFrame, length: int = 14) -> float:
    typical = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical * df['volume']
    delta = typical.diff()
    pos = money_flow.where(delta > 0, 0.0).rolling(length).sum()
    neg = money_flow.where(delta < 0, 0.0).rolling(length).sum()
    ratio = _ratio(_finite(pos.iloc[-1]), _finite(neg.iloc[-1]))
    return 100 - 100 / (1 + ratio) if neg.iloc[-1] else 100.0


def _cmf(df: pd.DataFrame, length: int = 20) -> float:
    high, low, close, volume = df['high'], df['low'], df['close'], df['volume']
    hl = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / hl
    mfv = (mfm * volume).fillna(0.0)
    denom = volume.rolling(length).sum().iloc[-1]
    return _finite(_ratio(_finite(mfv.rolling(length).sum().iloc[-1]), _finite(denom)))


def _stoch_k(df: pd.DataFrame, length: int = 14) -> float:
    low_min = df['low'].rolling(length).min().iloc[-1]
    high_max = df['high'].rolling(length).max().iloc[-1]
    return _finite(_ratio(df['close'].iloc[-1] - low_min, high_max - low_min) * 100, 50.0)


def _williams_r(df: pd.DataFrame, length: int = 14) -> float:
    low_min = df['low'].rolling(length).min().iloc[-1]
    high_max = df['high'].rolling(length).max().iloc[-1]
    return _finite(_ratio(high_max - df['close'].iloc[-1], high_max - low_min) * -100, -50.0)


def _cci(df: pd.DataFrame, length: int = 20) -> float:
    typical = (df['high'] + df['low'] + df['close']) / 3
    sma = typical.rolling(length).mean()
    mad = typical.rolling(length).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return _finite(_ratio(typical.iloc[-1] - sma.iloc[-1], 0.015 * mad.iloc[-1]))


def _macd_hist(close: pd.Series) -> float:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    return _finite((dif - dea).iloc[-1])


def _period_return(close: pd.Series, period: int) -> float:
    if len(close) <= period:
        return 0.0
    return _ratio(close.iloc[-1] - close.iloc[-1 - period], close.iloc[-1 - period]) * 100


def _volatility(close: pd.Series, length: int) -> float:
    returns = close.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    return _finite(returns.tail(length).std() * 100)


def _downside_vol(close: pd.Series, length: int) -> float:
    returns = close.pct_change().dropna().tail(length)
    negative = returns[returns < 0]
    if len(negative) < 2:
        return 0.0
    return _finite(negative.std() * 100)


def _max_drawdown(close: pd.Series, length: int) -> float:
    window = close.tail(length)
    if window.empty:
        return 0.0
    running_max = window.cummax()
    drawdown = (window - running_max) / running_max
    return _finite(drawdown.min() * 100)


# ------------------------------------------------------------------ 指标快照 ---


def compute_metrics(klines: list[dict[str, Any]]) -> dict[str, Any]:
    """
    根据历史K线计算全量因子指标快照。

    :param klines: [{date, open, high, low, close, volume}, ...] 时间升序，建议 >=60 根
    :return: 指标字典（各因子族的原始因子值），数据不足时返回 {'ok': False, ...}
    """
    df = klines_to_frame(klines)
    if len(df) < 20:
        return {'ok': False, 'reason': f'K线数据不足（{len(df)}<20），无法计算因子', 'historyCount': len(df)}

    close, high, low, volume = df['close'], df['high'], df['low'], df['volume']
    latest_close = _finite(close.iloc[-1])
    prev_close = _finite(close.iloc[-2]) if len(close) > 1 else latest_close

    def ma(length: int) -> float:
        return _finite(close.rolling(length).mean().iloc[-1]) if len(close) >= length else 0.0

    ma5, ma10, ma20, ma30 = ma(5), ma(10), ma(20), ma(30)
    ma60, ma120 = ma(60), ma(120)
    ema12 = _finite(close.ewm(span=12, adjust=False).mean().iloc[-1])
    ema26 = _finite(close.ewm(span=26, adjust=False).mean().iloc[-1])

    # 布林带 (20, 2)
    boll_mid = ma20
    boll_std = _finite(close.rolling(20).std().iloc[-1])
    boll_upper = boll_mid + 2 * boll_std
    boll_lower = boll_mid - 2 * boll_std
    boll_bandwidth = _ratio(boll_upper - boll_lower, boll_mid) * 100
    boll_percent_b = _ratio(latest_close - boll_lower, boll_upper - boll_lower) * 100 if boll_upper != boll_lower else 50.0

    # 区间位置 / 距高低点
    high20 = _finite(high.tail(20).max())
    low20 = _finite(low.tail(20).min())
    high60 = _finite(high.tail(60).max()) if len(df) >= 60 else high20
    low60 = _finite(low.tail(60).min()) if len(df) >= 60 else low20
    price_position20 = _ratio(latest_close - low20, high20 - low20) * 100 if high20 != low20 else 50.0
    price_position60 = _ratio(latest_close - low60, high60 - low60) * 100 if high60 != low60 else 50.0
    distance_high20 = _ratio(latest_close - high20, high20) * 100
    distance_high60 = _ratio(latest_close - high60, high60) * 100
    distance_low20 = _ratio(latest_close - low20, low20) * 100
    support_distance = abs(distance_low20)

    # 量能
    avg_volume5 = _finite(volume.tail(5).mean())
    avg_volume20 = _finite(volume.tail(20).mean())
    avg_volume60 = _finite(volume.tail(60).mean()) if len(df) >= 60 else avg_volume20
    latest_volume = _finite(volume.iloc[-1])
    volume_ratio5 = _ratio(latest_volume, avg_volume5)
    volume_ratio20 = _ratio(latest_volume, avg_volume20)
    volume_ratio60 = _ratio(latest_volume, avg_volume60)
    volume_trend20 = _ratio(avg_volume5 - avg_volume20, avg_volume20) * 100
    avg_dollar_volume20 = _finite((close * volume).tail(20).mean())
    close_volume_corr20 = _finite(close.tail(20).corr(volume.tail(20)))

    # VWAP(20)
    typical = (high + low + close) / 3
    vol_sum20 = _finite(volume.tail(20).sum())
    vwap20 = _ratio(_finite((typical * volume).tail(20).sum()), vol_sum20) if vol_sum20 else latest_close
    vwap_distance20 = _ratio(latest_close - vwap20, vwap20) * 100 if vwap20 else 0.0

    # K线形态
    latest_open = _finite(df['open'].iloc[-1])
    k_mid = _ratio(latest_close - latest_open, latest_open) * 100
    upper_shadow = _ratio(_finite(high.iloc[-1]) - max(latest_open, latest_close), latest_close) * 100
    lower_shadow = _ratio(min(latest_open, latest_close) - _finite(low.iloc[-1]), latest_close) * 100

    atr14 = _atr(df, 14)
    atr14_percent = _ratio(atr14, latest_close) * 100
    volatility20 = _volatility(close, 20)
    return20 = _period_return(close, 20)
    return_vol_ratio20 = _ratio(return20, volatility20)

    metrics: dict[str, Any] = {
        'ok': True,
        'tradeDate': df['date'].iloc[-1] if 'date' in df.columns else None,
        'historyCount': len(df),
        'latestClose': round(latest_close, 4),
        'dayChangePercent': round(_ratio(latest_close - prev_close, prev_close) * 100, 2),
        # 趋势
        'ma5': round(ma5, 4), 'ma10': round(ma10, 4), 'ma20': round(ma20, 4),
        'ma30': round(ma30, 4), 'ma60': round(ma60, 4), 'ma120': round(ma120, 4),
        'ema12': round(ema12, 4), 'ema26': round(ema26, 4),
        'return5': round(_period_return(close, 5), 2),
        'return20': round(return20, 2),
        'return60': round(_period_return(close, 60), 2),
        'returnVolatilityRatio20': round(return_vol_ratio20, 2),
        'maSlope20': round(_ratio(ma20 - ma(25), ma(25)) * 100 if len(close) >= 25 else 0.0, 2),
        'maSpread20_60': round(_ratio(ma20 - ma60, ma60) * 100, 2),
        'adx14': round(_adx(df, 14), 2),
        'macdHist': round(_macd_hist(close), 4),
        # 价型
        'kMid': round(k_mid, 2),
        'upperShadow': round(upper_shadow, 2),
        'lowerShadow': round(lower_shadow, 2),
        'pricePosition20': round(price_position20, 2),
        'pricePosition60': round(price_position60, 2),
        'bollMid20': round(boll_mid, 4), 'bollUpper20': round(boll_upper, 4), 'bollLower20': round(boll_lower, 4),
        'bollBandwidth20': round(boll_bandwidth, 2),
        'bollPercentB20': round(boll_percent_b, 2),
        'vwap20': round(vwap20, 4),
        'vwapDistance20': round(vwap_distance20, 2),
        # 动量
        'rsi6': round(_rsi(close, 6), 2),
        'rsi14': round(_rsi(close, 14), 2),
        'rsi28': round(_rsi(close, 28), 2),
        'roc12': round(_period_return(close, 12), 2),
        'stochK14': round(_stoch_k(df, 14), 2),
        'williamsR14': round(_williams_r(df, 14), 2),
        'cci20': round(_cci(df, 20), 2),
        # 突破
        'distanceHigh20': round(distance_high20, 2),
        'distanceHigh60': round(distance_high60, 2),
        'distanceLow20': round(distance_low20, 2),
        'supportDistance': round(support_distance, 2),
        # 量能资金
        'avgVolume5': round(avg_volume5, 2),
        'avgVolume20': round(avg_volume20, 2),
        'avgVolume60': round(avg_volume60, 2),
        'volumeRatio5': round(volume_ratio5, 2),
        'volumeRatio20': round(volume_ratio20, 2),
        'volumeRatio60': round(volume_ratio60, 2),
        'volumeTrend20': round(volume_trend20, 2),
        'avgDollarVolume20': round(avg_dollar_volume20, 2),
        'obvSlope20': round(_obv_slope(df, 20), 2),
        'mfi14': round(_mfi(df, 14), 2),
        'cmf20': round(_cmf(df, 20), 4),
        'closeVolumeCorr20': round(close_volume_corr20, 4),
        # 波动
        'volatility5': round(_volatility(close, 5), 2),
        'volatility20': round(volatility20, 2),
        'volatility60': round(_volatility(close, 60), 2),
        'atr14': round(atr14, 4),
        'atr14Percent': round(atr14_percent, 2),
        'downsideVol20': round(_downside_vol(close, 20), 2),
        'maxDrawdown20': round(_max_drawdown(close, 20), 2),
        'maxDrawdown60': round(_max_drawdown(close, 60), 2),
        # 高阶 Alpha 因子
        'alphaFactors': compute_alpha_factors(df),
    }
    return metrics


# ------------------------------------------------------------------ 打分 ---


def score_metrics(metrics: dict[str, Any], strategy_profile: str = 'balanced') -> dict[str, Any]:
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

    weights = PROFILE_WEIGHTS[profile]
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
    计算经典 WorldQuant Alpha101 及 Microsoft Qlib 高阶因子
    """
    if len(df) < 20:
        return {}

    close = df['close'].astype(float)
    open_p = df['open'].astype(float)
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    volume = df['volume'].astype(float)
    returns = close.pct_change()

    alpha_res = {}

    try:
        # Alpha006: -1 * correlation(open, volume, 10)
        cov = open_p.rolling(10).corr(volume).iloc[-1]
        alpha_res['alpha006'] = round(float(-1 * cov), 4) if not math.isnan(cov) else 0.0
    except Exception:
        alpha_res['alpha006'] = 0.0

    try:
        # Alpha012: sign(delta(volume, 1)) * (-1 * delta(close, 1))
        d_vol = volume.diff(1).iloc[-1]
        d_close = close.diff(1).iloc[-1]
        sign_vol = 1 if d_vol > 0 else (-1 if d_vol < 0 else 0)
        alpha_res['alpha012'] = round(float(sign_vol * (-1 * d_close)), 4)
    except Exception:
        alpha_res['alpha012'] = 0.0

    try:
        # Alpha054: (-1 * ((low - close) * (open^5))) / ((low - high) * (close^5))
        c5 = close.iloc[-1] ** 5
        o5 = open_p.iloc[-1] ** 5
        denom = (low.iloc[-1] - high.iloc[-1]) * c5
        numer = -1 * (low.iloc[-1] - close.iloc[-1]) * o5
        alpha_res['alpha054'] = round(float(numer / denom), 4) if denom != 0 else 0.0
    except Exception:
        alpha_res['alpha054'] = 0.0

    try:
        # Qlib-style 动量与波动率特征
        ret20 = returns.rolling(20).mean().iloc[-1]
        vol20 = returns.rolling(20).std().iloc[-1]
        alpha_res['qlib_sharpe20'] = round(float(ret20 / (vol20 + 1e-6)), 4)
        alpha_res['qlib_vol_spread'] = round(float(vol20 * math.sqrt(252)), 4)
    except Exception:
        alpha_res['qlib_sharpe20'] = 0.0
        alpha_res['qlib_vol_spread'] = 0.0

    return alpha_res


class FactorService:
    """
    因子引擎服务：整合 K线拉取 -> 指标计算 -> 打分。
    """

    @classmethod
    def get_factor_schema(cls) -> dict[str, Any]:
        """返回 8 大因子族体系定义（供前端展示）。"""
        return {
            'version': FACTOR_SCHEMA_VERSION,
            'familyCount': len(FACTOR_SCHEMA),
            'profiles': list(PROFILE_WEIGHTS.keys()),
            'families': FACTOR_SCHEMA,
        }

    @classmethod
    def compute_from_klines(
        cls, klines: list[dict[str, Any]], strategy_profile: str = 'balanced'
    ) -> dict[str, Any]:
        """
        对给定K线计算因子 + 打分（纯计算，不访问数据库/行情源）。

        :return: {'ok': bool, 'metrics': {...}, 'score': {...}} 或错误信息
        """
        metrics = compute_metrics(klines)
        if not metrics.get('ok'):
            return {'ok': False, 'reason': metrics.get('reason'), 'historyCount': metrics.get('historyCount', 0)}
        score = score_metrics(metrics, strategy_profile)
        return {'ok': True, 'metrics': metrics, 'score': score}

    @classmethod
    def compute_symbol(
        cls, symbol: str, market: str = 'US', strategy_profile: str = 'balanced', start: str = '-1y'
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
        result = cls.compute_from_klines(klines, strategy_profile)
        result['symbol'] = symbol
        result['market'] = market
        return result
