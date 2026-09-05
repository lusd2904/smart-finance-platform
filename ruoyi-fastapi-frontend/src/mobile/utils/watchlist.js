/** Watchlist overview helpers. Groups come from `items[].groups` or comma-split `note`. */

export function parseGroupNames(value) {
  if (Array.isArray(value)) return uniqueTrimmed(value)
  if (value == null || value === '') return []
  return uniqueTrimmed(String(value).split(/[,，]/))
}

function uniqueTrimmed(parts) {
  const seen = []
  for (const part of parts) {
    const s = String(part == null ? '' : part).trim()
    if (!s) continue
    if (!seen.includes(s)) seen.push(s)
  }
  return seen
}

export function itemGroups(item) {
  if (!item) return []
  const fromGroups = parseGroupNames(item.groups)
  if (fromGroups.length) return fromGroups
  return parseGroupNames(item.note)
}

export function filterItemsByGroup(items, groupName) {
  const list = Array.isArray(items) ? items : []
  const name = String(groupName || '').trim()
  if (!name) return list
  return list.filter((row) => itemGroups(row).includes(name))
}

export function overviewStats(overview) {
  const o = overview && typeof overview === 'object' ? overview : {}
  const items = Array.isArray(o.items) ? o.items : []
  return {
    count: Number.isFinite(Number(o.count)) ? Number(o.count) : items.length,
    bullish: Number(o.bullish) || 0,
    bearish: Number(o.bearish) || 0,
    neutral: Number(o.neutral) || 0
  }
}

export function overviewGroups(overview) {
  const raw = overview && Array.isArray(overview.groups) ? overview.groups : []
  return raw
    .map((g) => {
      if (typeof g === 'string') return { name: g.trim(), count: 0 }
      return { name: String(g?.name || '').trim(), count: Number(g?.count) || 0 }
    })
    .filter((g) => g.name)
}

export function sameWatch(a, b) {
  return String(a?.symbol || '').toUpperCase() === String(b?.symbol || '').toUpperCase()
    && String(a?.market || '').toUpperCase() === String(b?.market || '').toUpperCase()
}

export function watchIdsParam(ids) {
  if (Array.isArray(ids)) return ids.filter((id) => id != null && id !== '').join(',')
  return ids == null ? '' : String(ids)
}

export function noteFromGroup(name) {
  return String(name || '').trim()
}

export function isWatchlisted(items, symbol, market) {
  const list = Array.isArray(items) ? items : []
  return list.some((row) => sameWatch(row, { symbol, market }))
}
