export function unwrap(res) {
  return res?.data ?? res ?? {}
}

export function unwrapList(res) {
  const d = unwrap(res)
  if (Array.isArray(d)) return d
  return d.items || d.rows || d.list || d.records || d.jobs || d.signals || []
}

/** Dashboard section: `data` may already be an array, or `{ items }`. */
export function unwrapSectionList(section) {
  if (!section) return []
  const raw = section.data !== undefined ? section.data : section
  if (Array.isArray(raw)) return raw
  if (!raw || typeof raw !== 'object') return []
  return raw.items || raw.list || raw.rows || raw.records || []
}

export function unwrapTotal(res, fallback = 0) {
  const d = unwrap(res)
  return Number(d.total ?? d.count ?? fallback) || fallback
}

export function marketLabel(m) {
  if (m === 'US') return '美股'
  if (m === 'HK') return '港股'
  if (m === 'CN') return 'A股'
  return m || '--'
}

export function goTerminal(router, row, extra = {}) {
  if (!row?.symbol) {
    router.push('/trade/terminal')
    return
  }
  router.push({
    path: '/trade/terminal',
    query: { symbol: row.symbol, market: row.market || 'US', ...extra }
  })
}

export function goAiChat(router, row) {
  router.push({
    path: '/ai/chat',
    query: row?.symbol ? { symbol: row.symbol, market: row.market || 'US' } : {}
  })
}
