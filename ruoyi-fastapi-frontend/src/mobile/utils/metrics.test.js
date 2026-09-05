import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { lastBar, pickFirstNumber, coreMetrics, extraMetrics, needsTurnoverFallback, bidAskRatio, fmtRate } from './metrics.js'

describe('lastBar / pickFirstNumber', () => {
  it('takes the last bar and first finite number', () => {
    assert.equal(lastBar([]), null)
    assert.deepEqual(lastBar([{ close: 1 }, { close: 2 }]), { close: 2 })
    assert.equal(pickFirstNumber(null, '', 3.2), 3.2)
    assert.equal(pickFirstNumber(undefined, 'x'), null)
  })
})

describe('coreMetrics', () => {
  it('prefers the current-period last bar', () => {
    const cells = coreMetrics({
      bar: { high: 10, low: 8, open: 9, volume: 1000, turnover: 50000 },
      overview: { quote: { high: 99, prevClose: 8.5, turnover: 1 } },
      snapshot: { high: 77 }
    })
    const map = Object.fromEntries(cells.map((c) => [c.key, c.value]))
    assert.equal(map.high, 10)
    assert.equal(map.low, 8)
    assert.equal(map.open, 9)
    assert.equal(map.prevClose, 8.5)
    assert.equal(map.volume, 1000)
    assert.equal(map.turnover, 50000)
    assert.equal(needsTurnoverFallback(cells), false)
  })

  it('falls 成交额 back to overview then snapshot', () => {
    const fromOv = coreMetrics({
      bar: { high: 1, low: 1, open: 1, volume: 10 },
      overview: { quote: { turnover: 123 } }
    })
    assert.equal(fromOv.find((c) => c.key === 'turnover').value, 123)

    const fromSnap = coreMetrics({
      bar: { high: 1, low: 1, open: 1, volume: 10 },
      overview: { quote: {} },
      snapshot: { turnover: 456 }
    })
    assert.equal(fromSnap.find((c) => c.key === 'turnover').value, 456)
    assert.equal(needsTurnoverFallback(coreMetrics({ bar: { high: 1 } })), true)
  })
})

describe('extraMetrics', () => {
  it('keeps only fields that have values and maps camelCase snapshot keys', () => {
    const extra = extraMetrics({
      snapshot: {
        marketCap: 1e12,
        peTtm: 34.2,
        pb: 5.1,
        turnoverRate: 0.42,
        amplitude: 1.9,
        avgPrice: 225.1,
        volumeRatio: 0.88,
        high52: 260,
        low52: 169,
        beta: 1.12,
        dividendYield: 0.45,
        bidVolume: 80,
        askVolume: 20
      }
    })
    const keys = extra.map((c) => c.key)
    assert.deepEqual(keys, [
      'marketCap', 'pe', 'pb', 'turnoverRate', 'amplitude', 'avgPrice',
      'bidAsk', 'volumeRatio', 'high52', 'low52', 'beta', 'dividend'
    ])
    assert.equal(extra.find((c) => c.key === 'bidAsk').value, 60)
    assert.ok(extra.find((c) => c.key === 'pe').text.includes('34.20'))
  })

  it('omits empty extras', () => {
    assert.deepEqual(extraMetrics({ snapshot: { peTtm: null, name: '苹果' } }), [])
  })
})

describe('bidAskRatio / fmtRate', () => {
  it('uses packed ratio or bid/ask volumes', () => {
    assert.equal(bidAskRatio([{ bidAskRatio: 12 }]), 12)
    assert.equal(bidAskRatio([{ bidVolume: 3, askVolume: 1 }]), 50)
    assert.equal(bidAskRatio([{}]), null)
    assert.equal(fmtRate(1.2), '1.20%')
  })
})
