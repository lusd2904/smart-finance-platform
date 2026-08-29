"""
Alphalens 风格因子质检：截面 Spearman IC、IR 与分位收益。

不依赖已停更的 alphalens 包（与 pandas 2.x 不兼容），用 pandas 复现其核心指标：
- 前瞻收益 forward return（1/5/10 日）
- 每日截面 Spearman IC，再汇总 mean IC / IC std / IR
- 因子五分位平均前瞻收益与多空价差（Q5-Q1）

输入为「日期 × 标的」的收盘价/成交量面板，与原平台 Alphalens 提纯口径一致。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from module_market.constant.instruments import TARGET_INSTRUMENTS
from module_quant.dao.quant_dao import QuantFactorQcDao
from utils.influx_util import InfluxUtil
from utils.log_util import logger

QC_PERIODS = (1, 5, 10)
QC_QUANTILES = 5
MIN_CROSS_SECTION = 8
MIN_IC_DATES = 20
ENGINE_VERSION = 'alphalens-style-v1'


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(result) or np.isinf(result):
        return default
    return result


def _stack_panel(frame: pd.DataFrame) -> pd.Series:
    try:
        return frame.stack(future_stack=True)
    except TypeError:
        return frame.stack()


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    """无 scipy 依赖的 Spearman：对秩做 Pearson。"""
    aligned = pd.concat([left, right], axis=1, keys=['f', 'r']).dropna()
    if len(aligned) < MIN_CROSS_SECTION:
        return None
    corr = aligned['f'].rank().corr(aligned['r'].rank())
    return _finite(corr)


def _rsi_panel(close: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def factor_specs() -> list[dict[str, Any]]:
    """可质检的经典截面因子（与 8 大因子族中的动量/趋势/量能对应）。"""
    return [
        {
            'key': 'mom20',
            'label': '20日动量',
            'family': 'momentum',
            'func': lambda close, volume: close.pct_change(20),
        },
        {
            'key': 'reversal5',
            'label': '5日反转',
            'family': 'reversion',
            'func': lambda close, volume: -close.pct_change(5),
        },
        {
            'key': 'rsi14',
            'label': 'RSI14',
            'family': 'momentum',
            'func': lambda close, volume: _rsi_panel(close, 14),
        },
        {
            'key': 'ma_spread',
            'label': '均线差 MA20/MA60',
            'family': 'trend',
            'func': lambda close, volume: close.rolling(20).mean() / close.rolling(60).mean() - 1,
        },
        {
            'key': 'vol_ratio20',
            'label': '量比20',
            'family': 'volumeFlow',
            'func': lambda close, volume: volume / volume.rolling(20).mean(),
        },
        {
            'key': 'cs_mom20',
            'label': 'Alpha101 截面动量 rank',
            'family': 'alpha101Cs',
            'func': lambda close, volume: close.pct_change(20).rank(axis=1, pct=True),
        },
        {
            'key': 'cs_vol_ratio',
            'label': 'Alpha101 截面量比 rank',
            'family': 'alpha101Cs',
            'func': lambda close, volume: (volume / volume.rolling(20).mean()).rank(axis=1, pct=True),
        },
    ]


def forward_returns(close: pd.DataFrame, period: int) -> pd.DataFrame:
    """T 日因子对应 T→T+period 的前瞻收益（shift 负向对齐）。"""
    return close.pct_change(period).shift(-period)


def daily_information_coefficient(factor: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """每个交易日做一次截面 Spearman IC。"""
    dates = factor.index.intersection(fwd.index)
    ics: list[float] = []
    index: list[Any] = []
    for dt in dates:
        ic = _spearman(factor.loc[dt], fwd.loc[dt])
        if ic is None:
            continue
        ics.append(ic)
        index.append(dt)
    return pd.Series(ics, index=index, dtype=float)


def quantile_mean_returns(factor: pd.DataFrame, fwd: pd.DataFrame, quantiles: int = QC_QUANTILES) -> dict[str, float]:
    """把所有 (date, asset) 观测按因子分位，计算各分位平均前瞻收益。"""
    stacked = pd.concat(
        [_stack_panel(factor), _stack_panel(fwd)],
        axis=1,
        keys=['factor', 'fwd'],
    ).dropna()
    if stacked.empty or stacked['factor'].nunique() < quantiles:
        return {}
    try:
        stacked['q'] = pd.qcut(stacked['factor'], quantiles, labels=False, duplicates='drop')
    except ValueError:
        return {}
    means = stacked.groupby('q')['fwd'].mean()
    result: dict[str, float] = {}
    for q_idx, value in means.items():
        finite = _finite(value)
        if finite is None:
            continue
        result[f'q{int(q_idx) + 1}'] = round(finite * 100, 4)
    if 0 in means.index and means.index.max() is not None:
        hi = _finite(means.loc[means.index.max()])
        lo = _finite(means.loc[0])
        if hi is not None and lo is not None:
            result['spread'] = round((hi - lo) * 100, 4)
    return result


def evaluate_factor(
    factor: pd.DataFrame,
    close: pd.DataFrame,
    periods: tuple[int, ...] = QC_PERIODS,
    quantiles: int = QC_QUANTILES,
) -> list[dict[str, Any]]:
    """
    对单个因子面板做多周期质检。

    :return: [{horizon, icMean, icStd, ir, icPositiveRatio, sampleDates, symbolCount, quantiles, spread}, ...]
    """
    rows: list[dict[str, Any]] = []
    symbol_count = int(factor.shape[1])
    for period in periods:
        fwd = forward_returns(close, period)
        ics = daily_information_coefficient(factor, fwd)
        q_stats = quantile_mean_returns(factor, fwd, quantiles=quantiles)
        ic_mean = _finite(ics.mean()) if len(ics) else None
        ic_std = _finite(ics.std(ddof=1)) if len(ics) > 1 else None
        ir = None
        if ic_mean is not None and ic_std not in (None, 0.0) and abs(ic_std) > 1e-12:
            ir = round(ic_mean / ic_std, 4)
        positive_ratio = None
        if len(ics):
            positive_ratio = round(float((ics > 0).mean()), 4)
        rows.append(
            {
                'horizon': int(period),
                'icMean': round(ic_mean, 4) if ic_mean is not None else None,
                'icStd': round(ic_std, 4) if ic_std is not None else None,
                'ir': ir,
                'icPositiveRatio': positive_ratio,
                'sampleDates': len(ics),
                'symbolCount': symbol_count,
                'quantiles': q_stats,
                'spread': q_stats.get('spread'),
                'ok': bool(len(ics) >= MIN_IC_DATES and ic_mean is not None),
            }
        )
    return rows


def klines_to_panels(symbol_klines: dict[str, list[dict[str, Any]]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    把 {symbol: [kline, ...]} 转成 close/volume 宽表（index=date）。
    """
    close_frames: list[pd.Series] = []
    volume_frames: list[pd.Series] = []
    for symbol, rows in symbol_klines.items():
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        if 'date' not in frame.columns or 'close' not in frame.columns:
            continue
        frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
        frame = frame.dropna(subset=['date']).drop_duplicates(subset=['date']).set_index('date').sort_index()
        close_frames.append(pd.to_numeric(frame['close'], errors='coerce').rename(symbol))
        volume_col = frame['volume'] if 'volume' in frame.columns else pd.Series(0.0, index=frame.index)
        volume_frames.append(pd.to_numeric(volume_col, errors='coerce').rename(symbol))
    if not close_frames:
        return pd.DataFrame(), pd.DataFrame()
    close = pd.concat(close_frames, axis=1).sort_index()
    volume = pd.concat(volume_frames, axis=1).reindex(close.index).sort_index() if volume_frames else pd.DataFrame()
    return close, volume


class FactorQcService:
    """因子质检编排：拉全市场 K 线 → 计算 IC/IR → 落库。"""

    @classmethod
    def universe(cls, market: str = 'US') -> list[tuple[str, str]]:
        market = (market or 'US').upper()
        rows: list[tuple[str, str]] = []
        for symbol, _name, mkt, category in TARGET_INSTRUMENTS:
            if mkt != market:
                continue
            if category == 'index' or str(symbol).startswith('^'):
                continue
            rows.append((symbol, market))
        return rows

    @classmethod
    def load_close_volume(cls, market: str = 'US', start: str = '-280d', limit: int = 260) -> tuple[pd.DataFrame, pd.DataFrame]:
        symbols = [symbol for symbol, _mkt in cls.universe(market)]
        if not symbols:
            return pd.DataFrame(), pd.DataFrame()
        try:
            symbol_klines = InfluxUtil.query_klines_many(market, symbols, start=start, limit=limit)
        except Exception as exc:
            logger.warning(f'[因子质检] 批量K线失败 market={market}: {exc}')
            return pd.DataFrame(), pd.DataFrame()
        return klines_to_panels(symbol_klines or {})

    @classmethod
    def compute_qc_report(
        cls,
        close: pd.DataFrame,
        volume: pd.DataFrame,
        market: str = 'US',
        specs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if close.empty or close.shape[1] < MIN_CROSS_SECTION:
            return {
                'ok': False,
                'engine': ENGINE_VERSION,
                'market': market,
                'message': f'截面标的不足（需至少 {MIN_CROSS_SECTION} 只，当前 {int(close.shape[1])}）',
                'items': [],
                'asOf': None,
                'symbolCount': int(close.shape[1]),
            }
        items: list[dict[str, Any]] = []
        as_of = str(close.index.max().date()) if len(close.index) else None
        for spec in specs or factor_specs():
            func: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame] = spec['func']
            try:
                factor = func(close, volume)
            except Exception as exc:
                logger.warning(f'[因子质检] 计算 {spec["key"]} 失败: {exc}')
                continue
            if not isinstance(factor, pd.DataFrame):
                continue
            factor = factor.reindex(index=close.index, columns=close.columns)
            evaluations = evaluate_factor(factor, close)
            for row in evaluations:
                items.append(
                    {
                        'factorKey': spec['key'],
                        'factorLabel': spec['label'],
                        'family': spec.get('family'),
                        **row,
                    }
                )
        ok_count = sum(1 for it in items if it.get('ok'))
        return {
            'ok': ok_count > 0,
            'engine': ENGINE_VERSION,
            'market': market,
            'asOf': as_of,
            'symbolCount': int(close.shape[1]),
            'itemCount': len(items),
            'okCount': ok_count,
            'periods': list(QC_PERIODS),
            'message': '质检完成' if ok_count else '样本日期不足，IC 结果仅供参考',
            'items': items,
        }

    @classmethod
    def run_for_market(cls, market: str = 'US') -> dict[str, Any]:
        close, volume = cls.load_close_volume(market)
        return cls.compute_qc_report(close, volume, market=market)

    @classmethod
    async def persist_report(cls, db: AsyncSession, report: dict[str, Any]) -> int:
        saved = 0
        as_of = report.get('asOf')
        market = report.get('market') or 'US'
        for item in report.get('items') or []:
            payload = {
                'engine': report.get('engine'),
                'family': item.get('family'),
                'quantiles': item.get('quantiles') or {},
                'icPositiveRatio': item.get('icPositiveRatio'),
                'ok': item.get('ok'),
            }
            await QuantFactorQcDao.upsert(
                db,
                {
                    'factor_key': item.get('factorKey'),
                    'factor_label': item.get('factorLabel'),
                    'market': market,
                    'horizon': int(item.get('horizon') or 1),
                    'ic_mean': item.get('icMean'),
                    'ic_std': item.get('icStd'),
                    'ir': item.get('ir'),
                    'spread': item.get('spread'),
                    'sample_dates': item.get('sampleDates') or 0,
                    'symbol_count': item.get('symbolCount') or 0,
                    'as_of': as_of,
                    'quantile_json': json.dumps(item.get('quantiles') or {}, ensure_ascii=False),
                    'payload_json': json.dumps(payload, ensure_ascii=False, default=str),
                },
            )
            saved += 1
        await db.commit()
        return saved

    @classmethod
    async def run_and_store(cls, db: AsyncSession, market: str = 'US') -> dict[str, Any]:
        report = await _to_thread(cls.run_for_market, market)
        if report.get('items'):
            try:
                report['saved'] = await cls.persist_report(db, report)
            except Exception as exc:
                await db.rollback()
                logger.warning(f'[因子质检] 落库失败: {exc}')
                report['saved'] = 0
        else:
            report['saved'] = 0
        return report

    @classmethod
    async def latest_report(cls, db: AsyncSession, market: str = 'US') -> dict[str, Any]:
        rows = await QuantFactorQcDao.list_latest(db, market=market)
        items = []
        as_of = None
        for row in rows:
            quantiles: dict[str, Any] = {}
            if row.quantile_json:
                try:
                    quantiles = json.loads(row.quantile_json)
                except json.JSONDecodeError:
                    quantiles = {}
            payload: dict[str, Any] = {}
            if row.payload_json:
                try:
                    payload = json.loads(row.payload_json)
                except json.JSONDecodeError:
                    payload = {}
            items.append(
                {
                    'factorKey': row.factor_key,
                    'factorLabel': row.factor_label,
                    'family': payload.get('family'),
                    'horizon': row.horizon,
                    'icMean': row.ic_mean,
                    'icStd': row.ic_std,
                    'ir': row.ir,
                    'spread': row.spread,
                    'sampleDates': row.sample_dates,
                    'symbolCount': row.symbol_count,
                    'quantiles': quantiles,
                    'icPositiveRatio': payload.get('icPositiveRatio'),
                    'ok': payload.get('ok'),
                    'asOf': row.as_of,
                    'createTime': row.create_time.strftime('%Y-%m-%d %H:%M:%S') if row.create_time else None,
                }
            )
            as_of = as_of or row.as_of
        return {
            'ok': bool(items),
            'engine': ENGINE_VERSION,
            'market': market,
            'asOf': as_of,
            'itemCount': len(items),
            'items': items,
            'message': '已加载最近一次质检' if items else '暂无质检结果，请先运行因子质检',
        }


async def _to_thread(func: Callable[..., Any], *args: Any) -> Any:
    return await asyncio.to_thread(func, *args)
