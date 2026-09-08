export function safeRedirect(value, fallback = '/index') {
  if (typeof value !== 'string') return fallback
  if (!value.startsWith('/') || value.startsWith('//')) return fallback
  return value
}

export function terminalRoute(row = {}) {
  const symbol = row.symbol || row.code
  const market = row.market || undefined
  if (!symbol) return { path: '/trade/terminal' }
  return { path: '/trade/terminal', query: { symbol, ...(market ? { market } : {}) } }
}
