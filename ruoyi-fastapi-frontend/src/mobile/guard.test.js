import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { isForceMobileQuery, isMobilePath } from './guard.js'

describe('isMobilePath', () => {
  it('matches the /m tree only', () => {
    assert.equal(isMobilePath('/m'), true)
    assert.equal(isMobilePath('/m/login'), true)
    assert.equal(isMobilePath('/m/symbol/AAPL'), true)
    assert.equal(isMobilePath('/login'), false)
    assert.equal(isMobilePath('/market/heat'), false)
    assert.equal(isMobilePath('/me'), false)
  })
})

describe('isForceMobileQuery', () => {
  it('accepts ?m=1 and boolean true', () => {
    assert.equal(isForceMobileQuery({ m: '1' }), true)
    assert.equal(isForceMobileQuery({ m: 1 }), true)
    assert.equal(isForceMobileQuery({ m: 'true' }), true)
    assert.equal(isForceMobileQuery({ m: '0' }), false)
    assert.equal(isForceMobileQuery({}), false)
  })
})
