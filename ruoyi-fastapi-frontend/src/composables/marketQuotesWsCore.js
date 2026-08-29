/**
 * 行情 WS 纯函数：URL、订阅归一化、载荷分流、自选价补丁。
 * 不依赖 Vue，可供 Node 单测直接 import。
 */

export const MAX_SUBSCRIBE_SYMBOLS = 80

export function buildMarketQuotesWsUrl({ apiBase, protocol, host, intervalSec = 15 } = {}) {
  const clamped = Math.max(3, Math.min(60, Number(intervalSec) || 15))
  const base = apiBase || '/docker-api'
  const suffix = `/ws/market/quotes?interval=${clamped}`
  if (/^https?:\/\//i.test(base)) {
    const u = new URL(String(base).replace(/\/$/, '') + suffix)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return u.toString()
  }
  const proto = protocol === 'https:' ? 'wss:' : 'ws:'
  const path = `${String(base).replace(/\/$/, '')}${suffix}`
  return `${proto}//${host}${path}`
}

export function quoteKey(symbol, market) {
  return `${String(market || 'US').toUpperCase()}:${String(symbol || '').toUpperCase()}`
}

export function normalizeSubscribePairs(pairs) {
  const out = []
  const seen = new Set()
  for (const item of pairs || []) {
    let symbol = ''
    let market = 'US'
    if (typeof item === 'string') {
      const text = item.trim()
      if (text.includes(':')) {
        const [s, m] = text.split(':')
        symbol = s
        market = m || 'US'
      } else if (text.includes('.')) {
        const i = text.lastIndexOf('.')
        symbol = text.slice(0, i)
        market = text.slice(i + 1)
      } else {
        symbol = text
      }
    } else if (item && typeof item === 'object') {
      symbol = item.symbol
      market = item.market || 'US'
    }
    symbol = String(symbol || '').trim().toUpperCase()
    market = String(market || 'US').trim().toUpperCase()
    if (symbol.endsWith('.US')) {
      symbol = symbol.slice(0, -3)
      market = 'US'
    } else if (symbol.endsWith('.HK')) {
      symbol = symbol.slice(0, -3)
      market = 'HK'
    }
    if (!symbol) continue
    const key = quoteKey(symbol, market)
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ symbol, market })
    if (out.length >= MAX_SUBSCRIBE_SYMBOLS) break
  }
  return out
}

export function parseQuotesWsMessage(raw) {
  if (raw === 'ping' || raw === 'pong') return { kind: 'heartbeat', raw }
  let msg
  try {
    msg = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return { kind: 'raw', raw }
  }
  if (!msg || typeof msg !== 'object') return { kind: 'raw', raw }
  if (msg.channel === 'quotes') {
    return { kind: 'quotes', data: msg.quotes || {} }
  }
  if (msg.data) {
    return { kind: 'index', data: msg.data }
  }
  return { kind: 'other', data: msg }
}

export function applyQuotePatch(rows, liveItems) {
  if (!Array.isArray(rows) || !Array.isArray(liveItems) || !liveItems.length) return rows
  const map = new Map()
  for (const quote of liveItems) {
    if (!quote || !quote.symbol) continue
    map.set(quoteKey(quote.symbol, quote.market), quote)
  }
  return rows.map((row) => {
    const quote = map.get(quoteKey(row.symbol, row.market))
    if (!quote) return row
    const last = quote.last
    const changePct = quote.changePct ?? quote.changeRate
    return {
      ...row,
      last: last ?? row.last,
      price: last ?? row.price,
      changeRate: changePct ?? row.changeRate,
      changePct: changePct ?? row.changePct,
      quoteTime: quote.quoteTime || row.quoteTime,
      quoteSource: 'live',
    }
  })
}
