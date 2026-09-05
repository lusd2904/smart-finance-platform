export const UP = '#E5484D'
export const DOWN = '#30A46C'
export const FLAT = '#8B8D98'

export function changeTone(val) {
  const n = Number(val)
  if (!Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}

export function changeColor(val) {
  const tone = changeTone(val)
  if (tone === 'up') return UP
  if (tone === 'down') return DOWN
  return FLAT
}

export function fmtPct(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function fmtPrice(val, digits = 2) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  const d = abs >= 1000 ? 2 : abs >= 1 ? digits : Math.min(4, digits + 1)
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

export function fmtSigned(val, digits = 2) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const body = Math.abs(n).toFixed(digits)
  if (n > 0) return `+${body}`
  if (n < 0) return `-${body}`
  return body
}

export function fmtAmount(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(2)}万亿`
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)}万`
  return `${sign}${abs.toFixed(2)}`
}

export function fmtMoney(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function fmtTime(val) {
  if (!val) return ''
  const s = String(val)
  if (s.length >= 16) return s.slice(5, 16).replace('T', ' ')
  return s
}

export const MARKET_LABEL = { US: '美股', HK: '港股', CN: 'A股' }

export function marketLabel(market) {
  const m = String(market || '').toUpperCase()
  return MARKET_LABEL[m] || m || ''
}
