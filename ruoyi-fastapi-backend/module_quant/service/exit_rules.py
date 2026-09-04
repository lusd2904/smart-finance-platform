"""
Freqtrade-style exit stack for SFP position monitor (reimplemented; do not vendor freqtrade).

Reference: https://github.com/freqtrade/freqtrade
- hard `stoploss` → STOP_LOSS_PCT
- `minimal_roi` style fixed take-profit → TAKE_PROFIT_PCT
- `trailing_stop` / `trailing_stop_positive` + `trailing_stop_positive_offset`
  (activate trailing only after unrealized profit offset)
  → TRAILING_ACTIVATE_PCT / TRAILING_STOP_PCT

Priority if multiple fire on one tick: stop_loss > take_profit > trailing_stop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from utils.log_util import logger

STOP_LOSS_PCT = -8.0
TAKE_PROFIT_PCT = 15.0
TRAILING_ACTIVATE_PCT = 5.0
TRAILING_STOP_PCT = 3.0

# Redis peak price: sfp:exit:peak:{userId}:{market}:{symbol}
EXIT_PEAK_KEY_PREFIX = 'sfp:exit:peak'
EXIT_PEAK_TTL_SECONDS = 30 * 24 * 3600

ExitReason = Literal['stop_loss', 'take_profit', 'trailing_stop']

_REASON_TITLE = {
    'stop_loss': '持仓止损',
    'take_profit': '持仓止盈',
    'trailing_stop': '移动止盈',
}
_REASON_LEVEL = {
    'stop_loss': 'danger',
    'take_profit': 'success',
    'trailing_stop': 'warning',
}
_REASON_EVENT_LEVEL = {
    'stop_loss': 'danger',
    'take_profit': 'warning',
    'trailing_stop': 'warning',
}
_CYCLE_PREFIX = {
    'stop_loss': 'stoploss',
    'take_profit': 'takeprofit',
    'trailing_stop': 'trailing',
}


@dataclass(frozen=True)
class ExitRuleConfig:
    stop_loss_pct: float = STOP_LOSS_PCT
    take_profit_pct: float = TAKE_PROFIT_PCT
    trailing_activate_pct: float = TRAILING_ACTIVATE_PCT
    trailing_stop_pct: float = TRAILING_STOP_PCT

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None) -> ExitRuleConfig:
        """Optional overrides from user trade settings (keys ignored if absent)."""
        if not settings:
            return cls()
        return cls(
            stop_loss_pct=_setting_float(settings, 'stop_loss_pct', STOP_LOSS_PCT),
            take_profit_pct=_setting_float(settings, 'take_profit_pct', TAKE_PROFIT_PCT),
            trailing_activate_pct=_setting_float(settings, 'trailing_activate_pct', TRAILING_ACTIVATE_PCT),
            trailing_stop_pct=_setting_float(settings, 'trailing_stop_pct', TRAILING_STOP_PCT),
        )


DEFAULT_EXIT_RULES = ExitRuleConfig()


@dataclass(frozen=True)
class ExitDecision:
    reason: ExitReason
    pnl_pct: float
    peak: float
    peak_pnl_pct: float
    drawdown_pct: float

    @property
    def source(self) -> str:
        return self.reason

    @property
    def title_prefix(self) -> str:
        return _REASON_TITLE[self.reason]

    @property
    def level(self) -> str:
        return _REASON_LEVEL[self.reason]

    @property
    def event_level(self) -> str:
        return _REASON_EVENT_LEVEL[self.reason]

    @property
    def cycle_prefix(self) -> str:
        return _CYCLE_PREFIX[self.reason]


def ratchet_peak(peak: float | None, last: float) -> float:
    """Keep the high-water mark: max(stored peak, last). Invalid peak falls back to last."""
    if peak is None or peak <= 0:
        return last
    return max(peak, last)


def evaluate_position_exit(
    cost: float | None,
    last: float | None,
    peak: float | None,
    rules: ExitRuleConfig | None = None,
) -> ExitDecision | None:
    """Pure exit check vs cost / last / peak. None = hold.

    Trailing uses peak price (ratcheted with last). Drawdown is (peak - last) / peak,
    not vs cost. Trailing is armed only after peak PnL% vs cost reaches the offset.
    """
    cfg = rules or DEFAULT_EXIT_RULES
    if cost is None or last is None or cost <= 0 or last <= 0:
        return None
    peak_px = ratchet_peak(peak, last)
    if peak_px <= 0:
        return None
    pnl_pct = round((last - cost) / cost * 100.0, 4)
    peak_pnl_pct = round((peak_px - cost) / cost * 100.0, 4)
    drawdown_pct = round((peak_px - last) / peak_px * 100.0, 4)
    reason: ExitReason | None = None
    if pnl_pct <= cfg.stop_loss_pct:
        reason = 'stop_loss'
    elif pnl_pct >= cfg.take_profit_pct:
        reason = 'take_profit'
    elif peak_pnl_pct >= cfg.trailing_activate_pct and drawdown_pct >= cfg.trailing_stop_pct:
        reason = 'trailing_stop'
    if reason is None:
        return None
    return ExitDecision(
        reason=reason,
        pnl_pct=pnl_pct,
        peak=peak_px,
        peak_pnl_pct=peak_pnl_pct,
        drawdown_pct=drawdown_pct,
    )


def exit_peak_key(user_id: int, market: str, symbol: str) -> str:
    return f'{EXIT_PEAK_KEY_PREFIX}:{int(user_id)}:{market}:{symbol}'


def format_exit_trigger(decision: ExitDecision, rules: ExitRuleConfig | None = None) -> str:
    cfg = rules or DEFAULT_EXIT_RULES
    if decision.reason == 'stop_loss':
        return f'浮亏 {decision.pnl_pct}%，触发 {cfg.stop_loss_pct}% 止损线'
    if decision.reason == 'take_profit':
        return f'浮盈 {decision.pnl_pct}%，触发 {cfg.take_profit_pct}% 止盈线'
    return (
        f'浮盈 {decision.pnl_pct}%，峰值 {decision.peak} 回撤 {decision.drawdown_pct}%，'
        f'触发 {cfg.trailing_stop_pct}% 移动止损'
    )


async def load_exit_peak(user_id: int, market: str, symbol: str) -> float | None:
    redis = _redis()
    if redis is None:
        return None
    key = exit_peak_key(user_id, market, symbol)
    try:
        raw = await redis.get(key)
    except Exception as exc:
        logger.debug(f'[exit-peak] get {key} 失败: {exc}')
        return None
    return _as_float(raw)


async def store_exit_peak(user_id: int, market: str, symbol: str, peak: float) -> None:
    redis = _redis()
    if redis is None:
        return
    key = exit_peak_key(user_id, market, symbol)
    try:
        await redis.setex(key, EXIT_PEAK_TTL_SECONDS, str(peak))
    except Exception as exc:
        logger.debug(f'[exit-peak] set {key} 失败: {exc}')


async def clear_exit_peak(user_id: int, market: str, symbol: str) -> None:
    redis = _redis()
    if redis is None:
        return
    key = exit_peak_key(user_id, market, symbol)
    try:
        await redis.delete(key)
    except Exception as exc:
        logger.debug(f'[exit-peak] delete {key} 失败: {exc}')


def _redis() -> Any:
    try:
        from config.get_redis import RedisUtil

        return RedisUtil.get_client()
    except Exception:
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or result in (float('inf'), float('-inf')):
        return None
    return result


def _setting_float(settings: dict[str, Any], key: str, default: float) -> float:
    raw = settings.get(key)
    parsed = _as_float(raw)
    return default if parsed is None else parsed
