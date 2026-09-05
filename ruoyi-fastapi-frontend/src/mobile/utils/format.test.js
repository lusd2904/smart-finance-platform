import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { estimateNotional, fmtMoney } from './format.js'

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
