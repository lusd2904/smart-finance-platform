/** Client-only lot size: A-share 100, HK/US 1. Never invent lots when price or buying power is missing. */

export function lotSizeForMarket(market) {
  return String(market || '').toUpperCase() === 'CN' ? 100 : 1
}

export function cashCurrencyForMarket(market) {
  const m = String(market || '').toUpperCase()
  if (m === 'CN') return 'CNY'
  if (m === 'HK') return 'HKD'
  return 'USD'
}

/**
 * Map 25/50/75/100% to a share count.
 * Buy: floor(cash / price / lot) * lot, then take percent of lots.
 * Sell: sellable * percent, A-share floored to 100.
 * Missing price / cash / sellable → 0 (UI shows a tip).
 */
export function ticketQtyForPercent({ percent, side, market, price, cash, sellable }) {
  if (!percent || percent <= 0) return 0
  const lot = lotSizeForMarket(market)
  const pct = Math.min(100, Math.max(1, Number(percent) || 0))
  if (side === 'sell') {
    const avail = Number(sellable)
    if (!Number.isFinite(avail) || avail <= 0) return 0
    const raw = Math.floor((avail * pct) / 100)
    if (lot <= 1) return raw
    return Math.floor(raw / lot) * lot
  }
  const px = Number(price)
  const buyingPower = Number(cash)
  if (!Number.isFinite(px) || px <= 0 || !Number.isFinite(buyingPower) || buyingPower <= 0) {
    return 0
  }
  const maxShares = Math.floor(buyingPower / px / lot) * lot
  if (maxShares <= 0) return 0
  return Math.floor(((maxShares / lot) * pct) / 100) * lot
}

export function inferMarket(symbol, fallback = 'US') {
  const s = String(symbol || '').toUpperCase()
  if (s.endsWith('.HK') || s.includes('.HK')) return 'HK'
  if (s.endsWith('.US')) return 'US'
  if (s.endsWith('.SH') || s.endsWith('.SZ') || s.endsWith('.SS')) return 'CN'
  const code = s.split('.')[0]
  if (/^\d{6}/.test(code)) return 'CN'
  if (/^\d{1,5}$/.test(code)) return 'HK'
  return fallback || 'US'
}

export function quoteSymbol(symbol) {
  return String(symbol || '').split('.')[0]
}
