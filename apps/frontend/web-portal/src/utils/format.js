export function fmtNum(v, d = 2) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return n.toFixed(d)
}

export function fmtPx(v, d = 2) {
  return fmtNum(v, d)
}

export function fmtSigned(v, d = 2) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(d)}`
}

export function fmtChange(val) {
  const n = toSignedNumber(val)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function fmtSci(val, currency) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const text = n.toExponential(2)
  return currency ? `${text} ${currency}` : text
}

export function fmtCompact(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  if (abs >= 1e9) return `${(n / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(1)}万`
  return String(Math.round(n))
}

export function fmtCount(n) {
  return Number(n || 0).toLocaleString()
}

export function fmtAmount(val, currency) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  let text
  if (abs >= 1e12) text = `${(n / 1e12).toFixed(2)} 万亿`
  else if (abs >= 1e8) text = `${(n / 1e8).toFixed(2)} 亿`
  else if (abs >= 1e4) text = `${(n / 1e4).toFixed(2)} 万`
  else text = n.toFixed(2)
  return currency ? `${text} ${currency}` : text
}

export function formatVolume(vol) {
  const n = Number(vol)
  if (!Number.isFinite(n)) return '--'
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return String(Math.round(n))
}

export function formatTurnover(turnover) {
  return fmtAmount(turnover)
}

function toSignedNumber(val) {
  if (typeof val === 'string') {
    const n = Number(val.replace(/%/g, '').replace(/,/g, '').trim())
    return Number.isFinite(n) ? n : NaN
  }
  return Number(val)
}

export function changeClass(val) {
  const n = toSignedNumber(val)
  if (!Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}

export function sectionOk(section) {
  return Boolean(section && section.ok && section.data)
}

export function sectionReason(section, fallback = '暂无数据') {
  if (!section) return fallback
  return section.reason || fallback
}

export function pickNum(...vals) {
  for (const v of vals) {
    const n = Number(v)
    if (Number.isFinite(n)) return n
  }
  return 0
}

export function currencyOf(market) {
  if (market === 'US') return 'USD'
  if (market === 'HK') return 'HKD'
  return 'CNY'
}

/** Normalize a score to 0–100. Values in (0, 1] are treated as ratios. */
export function score100(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return null
  const raw = n > 0 && n <= 1 && !Number.isInteger(n) ? n * 100 : n
  return Math.max(0, Math.min(100, Math.round(raw)))
}

export function scoreClass(val) {
  const n = score100(val)
  if (n == null) return 'flat'
  if (n >= 60) return 'up'
  if (n <= 40) return 'down'
  return 'flat'
}

export function renderSparklinePath(arr) {
  const values = (arr || []).map(Number).filter(Number.isFinite)
  if (values.length < 2) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 60
      const y = 20 - ((v - min) / span) * 18
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')
}
