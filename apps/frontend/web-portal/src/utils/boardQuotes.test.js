import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { BOARD_TABLE_PAGE_SIZE, pageBoardRows, pickBoardLists } from './boardQuotes.js'

describe('pickBoardLists', () => {
  it('prefers payload.indices and featured/watch when present', () => {
    const picked = pickBoardLists({
      indices: [{ symbol: '^GSPC' }],
      featured: [{ symbol: 'AAPL' }],
      rows: [{ symbol: 'MSFT' }, { symbol: 'AAPL' }],
      count: 2
    })
    assert.equal(picked.indices[0].symbol, '^GSPC')
    assert.equal(picked.featured[0].symbol, 'AAPL')
    assert.equal(picked.rows.length, 2)
    assert.equal(picked.total, 2)
  })

  it('falls back to quotes when rows are missing', () => {
    const picked = pickBoardLists({ quotes: [{ symbol: '700.HK' }] })
    assert.equal(picked.rows[0].symbol, '700.HK')
    assert.deepEqual(picked.featured, [])
  })
})

describe('pageBoardRows', () => {
  it('never returns more than the page size from a 14k universe', () => {
    const universe = Array.from({ length: 14000 }, (_, i) => ({ symbol: `S${i}`, name: `Name ${i}` }))
    const paged = pageBoardRows(universe, { page: 1, pageSize: BOARD_TABLE_PAGE_SIZE })
    assert.equal(paged.rows.length, BOARD_TABLE_PAGE_SIZE)
    assert.equal(paged.filteredTotal, 14000)
    assert.equal(paged.showingFrom, 1)
    assert.equal(paged.showingTo, 50)
    assert.ok(paged.rows.length < 200)
  })

  it('search filters then pages, and clamps past-the-end pages', () => {
    const rows = [
      { symbol: 'AAPL', name: 'Apple' },
      { symbol: 'MSFT', name: 'Microsoft' },
      { symbol: 'NVDA', name: 'NVIDIA' }
    ]
    const found = pageBoardRows(rows, { keyword: 'app', page: 9, pageSize: 50 })
    assert.equal(found.rows.length, 1)
    assert.equal(found.rows[0].symbol, 'AAPL')
    assert.equal(found.page, 1)
    assert.equal(found.filteredTotal, 1)
  })
})
