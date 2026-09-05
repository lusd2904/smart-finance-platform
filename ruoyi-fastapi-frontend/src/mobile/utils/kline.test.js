import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { KLINE_PERIODS, pickKlineBars, isKlinePeriod } from './kline.js'

describe('KLINE_PERIODS', () => {
  it('covers intraday / daily / weekly / monthly', () => {
    assert.deepEqual(KLINE_PERIODS.map((p) => p.key), ['intraday', 'daily', 'weekly', 'monthly'])
    assert.equal(isKlinePeriod('weekly'), true)
    assert.equal(isKlinePeriod('5min'), false)
  })
})

describe('pickKlineBars', () => {
  it('unwraps camelCase bars with turnover fallback', () => {
    const bars = pickKlineBars({
      data: {
        klines: [
          { date: '2026-09-01', open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, amount: 20 },
          { time: '09:31', open: 2, high: 3, low: 1, last: 2.5, volume: 11, turnover: 30 }
        ]
      }
    })
    assert.equal(bars.length, 2)
    assert.deepEqual(bars[0], { date: '2026-09-01', open: 1, high: 2, low: 0.5, close: 1.5, volume: 10, turnover: 20 })
    assert.equal(bars[1].close, 2.5)
    assert.equal(bars[1].turnover, 30)
    assert.equal(bars[1].date, '09:31')
  })
})
