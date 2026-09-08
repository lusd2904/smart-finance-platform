export function unwrap(res) {
  return res?.data ?? res ?? {}
}

export function unwrapList(res) {
  const d = unwrap(res)
  if (Array.isArray(d)) return d
  return d.items || d.rows || d.list || d.records || d.jobs || []
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
