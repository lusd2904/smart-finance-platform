"""长桥账户多币种 → 美元基准换算（自动交易护栏用）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.log_util import logger

FALLBACK_USD_HKD = 7.80
FALLBACK_USD_CNY = 7.20


def _normalize_fx_pair_rate(symbol: str, last: float) -> float | None:
    """解析 USDHKD / USDCNH 等报价；last < 1 时视为反向报价。"""
    if last <= 0:
        return None
    sym = str(symbol or '').strip().upper()
    rate = 1.0 / last if last < 1 else last
    if sym in {'HKDUSD', 'CNHUSD', 'CNYUSD'}:
        rate = last if last >= 1 else 1.0 / last
    return rate


@dataclass
class FxRates:
    """美元兑各交易币种汇率（1 USD = usd_hkd HKD）。"""

    usd_hkd: float = FALLBACK_USD_HKD
    usd_cny: float = FALLBACK_USD_CNY
    sources: dict[str, str] = field(default_factory=dict)

    def to_usd(self, amount: float, currency: str | None) -> float:
        cur = str(currency or 'USD').strip().upper()
        value = float(amount or 0)
        if value == 0:
            return 0.0
        if cur in {'USD', 'US'}:
            return value
        if cur == 'HKD':
            return value / self.usd_hkd if self.usd_hkd else value
        if cur in {'CNY', 'CNH', 'CN'}:
            return value / self.usd_cny if self.usd_cny else value
        logger.warning(f'[FX] 未知币种 {cur!r}，按 USD 1:1 计入护栏')
        return value

    def from_usd(self, amount_usd: float, currency: str | None) -> float:
        cur = str(currency or 'USD').strip().upper()
        value = float(amount_usd or 0)
        if value == 0:
            return 0.0
        if cur in {'USD', 'US'}:
            return value
        if cur == 'HKD':
            return value * self.usd_hkd
        if cur in {'CNY', 'CNH', 'CN'}:
            return value * self.usd_cny
        logger.warning(f'[FX] 未知币种 {cur!r}，按 USD 1:1 还原下单金额')
        return value

    def order_currency(self, market: str | None) -> str:
        mkt = str(market or 'US').strip().upper()
        return 'HKD' if mkt == 'HK' else 'USD'

    def as_snapshot(self) -> dict[str, Any]:
        return {
            'USDHKD': round(self.usd_hkd, 6),
            'USDCNH': round(self.usd_cny, 6),
            'USDHKD_source': self.sources.get('USDHKD', 'fallback'),
            'USDCNH_source': self.sources.get('USDCNH', 'fallback'),
        }


def _pick_rate_from_quotes(quotes: list[dict[str, Any]], pair: str, fallback: float) -> tuple[float, str]:
    target = pair.upper()
    alt = {'USDCNH': 'USDCNY', 'USDCNY': 'USDCNH'}.get(target, '')
    for q in quotes or []:
        sym = str(q.get('symbol') or '').upper().replace('.', '')
        if sym not in {target, alt}:
            continue
        last = q.get('lastDone')
        if last is None:
            last = q.get('last')
        try:
            parsed = _normalize_fx_pair_rate(sym, float(last))
        except (TypeError, ValueError):
            parsed = None
        if parsed and parsed > 0:
            return parsed, 'longbridge'
    logger.warning(f'[FX] 长桥未返回 {pair}，使用兜底汇率 {fallback}')
    return fallback, 'fallback'


async def load_fx_rates_async() -> FxRates:
    """从长桥实时行情拉取 USDHKD / USDCNH；失败则记录日志并使用兜底。"""
    from module_quant.service.longbridge_service import LongbridgeService

    rates = FxRates()
    if not LongbridgeService.is_configured():
        rates.sources = {'USDHKD': 'fallback', 'USDCNH': 'fallback'}
        return rates
    try:
        quote = await LongbridgeService.get_realtime_quote_async(['USDHKD', 'USDCNH'], 'US')
        quotes = quote.get('quotes') or []
        rates.usd_hkd, hkd_src = _pick_rate_from_quotes(quotes, 'USDHKD', FALLBACK_USD_HKD)
        rates.usd_cny, cny_src = _pick_rate_from_quotes(quotes, 'USDCNH', FALLBACK_USD_CNY)
        rates.sources = {'USDHKD': hkd_src, 'USDCNH': cny_src}
    except Exception as exc:
        logger.warning(f'[FX] 拉取长桥汇率失败，使用兜底: {exc}')
        rates.sources = {'USDHKD': 'fallback', 'USDCNH': 'fallback'}
    return rates


def sum_balance_field_usd(
    account_result: dict[str, Any] | None,
    field: str,
    fx: FxRates,
    *,
    cash_fallback: bool = False,
) -> float:
    """汇总各币种余额切片并换算为美元。"""
    balances = (account_result or {}).get('balances') or []
    if not balances:
        from module_quant.service.longbridge_service import LongbridgeService

        flat = LongbridgeService.flatten_account(account_result or {})
        raw = flat.get(field)
        if raw is None and cash_fallback:
            raw = flat.get('availableCash') or flat.get('totalCash')
        if raw is None:
            return 0.0
        return round(fx.to_usd(float(raw or 0), flat.get('currency')), 2)
    total = 0.0
    for row in balances:
        raw = row.get(field)
        if raw is None and cash_fallback:
            raw = row.get('availableCash') or row.get('totalCash')
        total += fx.to_usd(float(raw or 0), row.get('currency'))
    return round(total, 2)


def pick_net_assets_usd(account_result: dict[str, Any] | None, fx: FxRates) -> float:
    return sum_balance_field_usd(account_result, 'netAssets', fx, cash_fallback=True)


def pick_available_cash_usd(account_result: dict[str, Any] | None, fx: FxRates) -> float:
    return sum_balance_field_usd(account_result, 'availableCash', fx, cash_fallback=True)


def raw_balance_rows(account_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    balances = (account_result or {}).get('balances') or []
    rows: list[dict[str, Any]] = []
    for row in balances:
        rows.append(
            {
                'currency': row.get('currency'),
                'totalCash': float(row.get('totalCash') or 0),
                'availableCash': float(row.get('availableCash') or row.get('totalCash') or 0),
                'netAssets': float(row.get('netAssets') or row.get('availableCash') or row.get('totalCash') or 0),
            }
        )
    return rows


def account_guardrail_snapshot(
    account_result: dict[str, Any] | None,
    fx: FxRates,
) -> dict[str, Any]:
    return {
        'balanceByCurrency': raw_balance_rows(account_result),
        'netAssetsUsd': pick_net_assets_usd(account_result, fx),
        'availableCashUsd': pick_available_cash_usd(account_result, fx),
        'fxRates': fx.as_snapshot(),
    }
