export function terminalRoute(row = {}) {
  const symbol = row.symbol || row.code
  const market = row.market || undefined
  if (!symbol) return { path: '/trade/terminal' }
  return { path: '/trade/terminal', query: { symbol, ...(market ? { market } : {}) } }
}
