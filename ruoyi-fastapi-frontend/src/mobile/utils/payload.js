/** Unwrap RuoYi `{ code, data }` and table `{ rows }` envelopes without inventing a second contract. */

export function unwrapData(res) {
  if (!res || typeof res !== 'object') return {}
  if (res.data && typeof res.data === 'object' && !Array.isArray(res.data)) return res.data
  return res
}

export function unwrapList(res, keys = ['items', 'rows', 'data', 'list', 'top50', 'positions', 'klines']) {
  if (Array.isArray(res)) return res
  if (Array.isArray(res?.rows)) return res.rows
  if (Array.isArray(res?.data) && !res.data.klines) return res.data
  const payload = unwrapData(res)
  if (Array.isArray(payload)) return payload
  for (const k of keys) {
    if (Array.isArray(payload[k])) return payload[k]
  }
  if (Array.isArray(res?.data?.rows)) return res.data.rows
  return []
}

export function unwrapRows(res) {
  if (Array.isArray(res?.rows)) return res.rows
  if (Array.isArray(res?.data?.rows)) return res.data.rows
  return unwrapList(res, ['rows', 'items', 'data'])
}

export function num(v, fallback = null) {
  if (v == null || v === '') return fallback
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

export function str(v, fallback = '') {
  if (v == null) return fallback
  const s = String(v)
  return s === 'null' || s === 'undefined' ? fallback : s
}
