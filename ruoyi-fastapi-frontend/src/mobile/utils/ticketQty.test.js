import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { lotSizeForMarket, ticketQtyForPercent, inferMarket } from './ticketQty.js'

describe('lotSizeForMarket', () => {
  it('uses 100 for CN and 1 for HK/US', () => {
    assert.equal(lotSizeForMarket('CN'), 100)
    assert.equal(lotSizeForMarket('HK'), 1)
    assert.equal(lotSizeForMarket('US'), 1)
  })
})

describe('ticketQtyForPercent', () => {
  it('returns 0 when buy price or cash is missing', () => {
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'US', price: null, cash: 10000 }), 0)
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'US', price: 10, cash: null }), 0)
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'US', price: 0, cash: 10000 }), 0)
  })

  it('floors US buy lots to whole shares', () => {
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'US', price: 10, cash: 105 }), 10)
    assert.equal(ticketQtyForPercent({ percent: 50, side: 'buy', market: 'US', price: 10, cash: 100 }), 5)
  })

  it('floors CN buy lots to 100', () => {
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'CN', price: 10, cash: 2500 }), 200)
    assert.equal(ticketQtyForPercent({ percent: 25, side: 'buy', market: 'CN', price: 10, cash: 10000 }), 200)
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'buy', market: 'CN', price: 10, cash: 99 }), 0)
  })

  it('sells A-share in lots of 100 and never invents qty', () => {
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'sell', market: 'CN', sellable: 350 }), 300)
    assert.equal(ticketQtyForPercent({ percent: 50, side: 'sell', market: 'CN', sellable: 350 }), 100)
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'sell', market: 'CN', sellable: 0 }), 0)
    assert.equal(ticketQtyForPercent({ percent: 100, side: 'sell', market: 'US', sellable: 7 }), 7)
  })
})

describe('inferMarket', () => {
  it('reads suffix and numeric codes', () => {
    assert.equal(inferMarket('0700.HK'), 'HK')
    assert.equal(inferMarket('600519'), 'CN')
    assert.equal(inferMarket('AAPL'), 'US')
  })
})
