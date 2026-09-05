import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  parseGroupNames,
  itemGroups,
  filterItemsByGroup,
  overviewStats,
  overviewGroups,
  sameWatch,
  watchIdsParam,
  noteFromGroup,
  isWatchlisted
} from './watchlist.js'

describe('parseGroupNames', () => {
  it('splits comma / Chinese comma and de-dupes', () => {
    assert.deepEqual(parseGroupNames('七巨头,光'), ['七巨头', '光'])
    assert.deepEqual(parseGroupNames('七巨头，持仓,七巨头'), ['七巨头', '持仓'])
    assert.deepEqual(parseGroupNames(['核心', ' 持仓 ', '核心']), ['核心', '持仓'])
    assert.deepEqual(parseGroupNames(''), [])
    assert.deepEqual(parseGroupNames(null), [])
  })
})

describe('itemGroups / filterItemsByGroup', () => {
  const items = [
    { symbol: 'AAPL', groups: ['科技'], note: 'ignored' },
    { symbol: '0700', note: '科技,持仓' },
    { symbol: '600519', groups: [], note: '消费' }
  ]

  it('prefers groups[] then falls back to note', () => {
    assert.deepEqual(itemGroups(items[0]), ['科技'])
    assert.deepEqual(itemGroups(items[1]), ['科技', '持仓'])
    assert.deepEqual(itemGroups(items[2]), ['消费'])
  })

  it('filters by group and treats empty as 全部', () => {
    assert.equal(filterItemsByGroup(items, '').length, 3)
    assert.deepEqual(filterItemsByGroup(items, '科技').map((r) => r.symbol), ['AAPL', '0700'])
    assert.deepEqual(filterItemsByGroup(items, '消费').map((r) => r.symbol), ['600519'])
    assert.deepEqual(filterItemsByGroup(items, '空分组'), [])
  })
})

describe('overviewStats / overviewGroups', () => {
  it('reads count / stance / group chips', () => {
    const ov = {
      count: 4,
      bullish: 2,
      bearish: 1,
      neutral: 1,
      groups: [{ name: '科技', count: 3 }, { name: '消费', count: 1 }],
      items: [{}, {}, {}, {}]
    }
    assert.deepEqual(overviewStats(ov), { count: 4, bullish: 2, bearish: 1, neutral: 1 })
    assert.deepEqual(overviewGroups(ov), [{ name: '科技', count: 3 }, { name: '消费', count: 1 }])
  })

  it('falls count back to items.length', () => {
    assert.deepEqual(overviewStats({ items: [{}, {}] }), { count: 2, bullish: 0, bearish: 0, neutral: 0 })
  })
})

describe('sameWatch / watchIdsParam / noteFromGroup', () => {
  it('matches symbol+market and joins delete ids', () => {
    assert.equal(sameWatch({ symbol: 'aapl', market: 'us' }, { symbol: 'AAPL', market: 'US' }), true)
    assert.equal(sameWatch({ symbol: 'AAPL', market: 'US' }, { symbol: 'AAPL', market: 'HK' }), false)
    assert.equal(watchIdsParam([1, 2, 3]), '1,2,3')
    assert.equal(watchIdsParam(9), '9')
    assert.equal(noteFromGroup(' 核心 '), '核心')
    assert.equal(noteFromGroup(''), '')
  })

  it('detects already-watchlisted rows', () => {
    const items = [{ symbol: 'AAPL', market: 'US' }]
    assert.equal(isWatchlisted(items, 'aapl', 'us'), true)
    assert.equal(isWatchlisted(items, 'NVDA', 'US'), false)
  })
})
