/** Symbol metrics grid: last bar of the current period, then overview / snapshot. */

import { num } from './payload.js'
import { fmtAmount, fmtPrice } from './format.js'

export function lastBar(bars) {
  const list = Array.isArray(bars) ? bars : []
  return list.length ? list[list.length - 1] : null
}

export function pickFirstNumber(...vals) {
  for (const v of vals) {
    const n = num(v)
    if (n != null) return n
  }
  return null
}

export function flattenQuoteSources(overview, snapshot) {
  const ov = overview && typeof overview === 'object' ? overview : {}
  const quote = ov.quote && typeof ov.quote === 'object' && !Array.isArray(ov.quote) ? ov.quote : ov
  const snap = snapshot && typeof snapshot === 'object' ? snapshot : {}
  const snapQuote = snap.quote && typeof snap.quote === 'object' ? snap.quote : {}
  return { ov, quote, snap, snapQuote }
}

function pickFrom(sources, keys) {
  for (const src of sources) {
    if (!src || typeof src !== 'object') continue
    for (const key of keys) {
      const n = num(src[key])
      if (n != null) return n
    }
  }
  return null
}

export function bidAskRatio(sources) {
  const packed = pickFrom(sources, ['bidAskRatio', 'commissionRatio', 'orderRatio'])
  if (packed != null) return packed
  for (const src of sources) {
    if (!src || typeof src !== 'object') continue
    const bid = pickFirstNumber(src.bidVolume, src.bidVol, src.totalBid)
    const ask = pickFirstNumber(src.askVolume, src.askVol, src.totalAsk)
    if (bid == null || ask == null) continue
    const den = bid + ask
    if (!den) continue
    return ((bid - ask) / den) * 100
  }
  return null
}

export function fmtRate(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return `${n.toFixed(2)}%`
}

export function fmtPlain(val, digits = 2) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return n.toFixed(digits)
}

function formatMetric(value, kind) {
  if (kind === 'amount') return fmtAmount(value)
  if (kind === 'price') return fmtPrice(value)
  if (kind === 'pct') return fmtRate(value)
  if (kind === 'num4') return fmtPlain(value, 4)
  return fmtPlain(value, 2)
}

export function coreMetrics({ bar, overview, snapshot } = {}) {
  const { ov, quote, snap, snapQuote } = flattenQuoteSources(overview, snapshot)
  const sources = [bar, quote, ov, snap, snapQuote]
  const high = pickFrom(sources, ['high'])
  const low = pickFrom(sources, ['low'])
  const open = pickFrom(sources, ['open'])
  const prevClose = pickFrom(sources, ['prevClose', 'preClose'])
  const volume = pickFrom(sources, ['volume'])
  const turnover = pickFrom(sources, ['turnover', 'amount', 'turnoverValue'])
  return [
    { key: 'high', label: '最高', value: high, text: fmtPrice(high) },
    { key: 'low', label: '最低', value: low, text: fmtPrice(low) },
    { key: 'open', label: '今开', value: open, text: fmtPrice(open) },
    { key: 'prevClose', label: '昨收', value: prevClose, text: fmtPrice(prevClose) },
    { key: 'volume', label: '成交量', value: volume, text: fmtAmount(volume) },
    { key: 'turnover', label: '成交额', value: turnover, text: fmtAmount(turnover) }
  ]
}

export function extraMetrics({ overview, snapshot } = {}) {
  const { ov, quote, snap, snapQuote } = flattenQuoteSources(overview, snapshot)
  const sources = [snap, snapQuote, quote, ov]
  const fields = [
    { key: 'marketCap', label: '市值', value: pickFrom(sources, ['marketCap', 'floatMarketCap']), kind: 'amount' },
    { key: 'pe', label: 'PE', value: pickFrom(sources, ['peTtm', 'pe', 'peStatic', 'peDynamic']), kind: 'num' },
    { key: 'pb', label: 'PB', value: pickFrom(sources, ['pb', 'pbRatio']), kind: 'num' },
    { key: 'turnoverRate', label: '换手', value: pickFrom(sources, ['turnoverRate']), kind: 'pct' },
    { key: 'amplitude', label: '振幅', value: pickFrom(sources, ['amplitude']), kind: 'pct' },
    { key: 'avgPrice', label: '均价', value: pickFrom(sources, ['avgPrice']), kind: 'price' },
    { key: 'bidAsk', label: '委比', value: bidAskRatio(sources), kind: 'pct' },
    { key: 'volumeRatio', label: '量比', value: pickFrom(sources, ['volumeRatio']), kind: 'num' },
    { key: 'high52', label: '52周高', value: pickFrom(sources, ['high52', 'week52High', 'fiftyTwoWeekHigh']), kind: 'price' },
    { key: 'low52', label: '52周低', value: pickFrom(sources, ['low52', 'week52Low', 'fiftyTwoWeekLow']), kind: 'price' },
    { key: 'beta', label: 'Beta', value: pickFrom(sources, ['beta']), kind: 'num4' },
    { key: 'dividend', label: '股息', value: pickFrom(sources, ['dividendYield', 'dividendYieldTtm', 'dividend']), kind: 'pct' }
  ]
  return fields.filter((f) => f.value != null).map((f) => ({
    key: f.key,
    label: f.label,
    value: f.value,
    text: formatMetric(f.value, f.kind)
  }))
}

export function needsTurnoverFallback(cells) {
  const cell = (cells || []).find((c) => c.key === 'turnover')
  return !cell || cell.value == null
}
