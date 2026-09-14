export const BOARD_TABLE_PAGE_SIZE = 50
export const BOARD_TABLE_MAX_PAGE_SIZE = 100

function asRows(value) {
  return Array.isArray(value) ? value : []
}

function firstNamedRows(data, keys) {
  for (const key of keys) {
    const rows = asRows(data?.[key])
    if (rows.length) return rows
  }
  return []
}

/** Pull indices + optional featured/watch subset + full quote list from /market/board/quotes. */
export function pickBoardLists(payload) {
  const data = payload && typeof payload === 'object' ? payload : {}
  const indices = asRows(data.indices)
  const featured = firstNamedRows(data, ['featured', 'featuredRows', 'featuredQuotes', 'watch', 'watchlist', 'watchRows'])
  const quotes = firstNamedRows(data, ['rows', 'quotes'])
  return {
    indices,
    featured,
    rows: quotes,
    total: Number(data.count) || quotes.length
  }
}

/** Filter then slice so el-table never mounts the full universe. */
export function pageBoardRows(rows, { keyword = '', page = 1, pageSize = BOARD_TABLE_PAGE_SIZE } = {}) {
  const list = asRows(rows)
  const kw = String(keyword || '').trim().toLowerCase()
  const filtered = kw
    ? list.filter((r) => `${r?.symbol || ''} ${r?.name || ''}`.toLowerCase().includes(kw))
    : list
  const total = filtered.length
  const size = Math.min(
    BOARD_TABLE_MAX_PAGE_SIZE,
    Math.max(1, Number(pageSize) || BOARD_TABLE_PAGE_SIZE)
  )
  const maxPage = Math.max(1, Math.ceil(total / size) || 1)
  const current = Math.min(Math.max(1, Number(page) || 1), maxPage)
  const start = (current - 1) * size
  const pageRows = filtered.slice(start, start + size)
  return {
    rows: pageRows,
    filteredTotal: total,
    page: current,
    pageSize: size,
    showingFrom: total ? start + 1 : 0,
    showingTo: Math.min(start + size, total)
  }
}
