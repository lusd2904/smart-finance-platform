import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { estimateNotional, fmtMoney, fmtPrice, fmtPct } from './format.js'

describe('fmtPrice', () => {
  it('shows -- for missing or non-finite prices, not 0.000', () => {
    assert.equal(fmtPrice(null), '--')
    assert.equal(fmtPrice(undefined), '--')
    assert.equal(fmtPrice(''), '--')
    assert.equal(fmtPrice(NaN), '--')
    assert.equal(fmtPrice('abc'), '--')
  })

  it('keeps an explicit numeric 0 from a valid quote', () => {
    assert.equal(fmtPrice(0), '0.000')
    assert.equal(fmtPrice('0'), '0.000')
    assert.equal(fmtPrice('0.000'), '0.000')
  })

  it('formats ordinary last prices', () => {
    assert.equal(fmtPrice(226.4), '226.40')
    assert.equal(fmtPrice(0.512), '0.512')
  })
})

describe('fmtPct', () => {
  it('keeps changePct when present', () => {
    assert.equal(fmtPct(1.35), '+1.35%')
    assert.equal(fmtPct(-0.42), '-0.42%')
    assert.equal(fmtPct(0), '+0.00%')
  })
})

describe('estimateNotional', () => {
  it('returns -- when price is missing or qty is 0', () => {
    assert.equal(estimateNotional(null, 100), '--')
    assert.equal(estimateNotional('', 100), '--')
    assert.equal(estimateNotional(10, 0), '--')
    assert.equal(estimateNotional(10, ''), '--')
    assert.equal(estimateNotional(0, 100), '--')
  })

  it('formats limit × qty and updates when qty is typed', () => {
    assert.equal(estimateNotional(226.4, 10), fmtMoney(2264))
    assert.equal(estimateNotional('10.5', '20'), fmtMoney(210))
    assert.equal(estimateNotional(10, 1.9), fmtMoney(10))
  })
})
