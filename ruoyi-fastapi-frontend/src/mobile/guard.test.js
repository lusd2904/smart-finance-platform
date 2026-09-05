import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { isForceMobileQuery, isForcePcQuery, isMobilePath, parseMFlag } from './guard.js'

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

describe('parseMFlag', () => {
  it('maps 1 / 0 and leaves other values alone', () => {
    assert.equal(parseMFlag('1'), 1)
    assert.equal(parseMFlag(1), 1)
    assert.equal(parseMFlag('true'), 1)
    assert.equal(parseMFlag('0'), 0)
    assert.equal(parseMFlag(0), 0)
    assert.equal(parseMFlag('false'), 0)
    assert.equal(parseMFlag(''), null)
    assert.equal(parseMFlag(undefined), null)
  })
})

describe('isForceMobileQuery / isForcePcQuery', () => {
  it('splits ?m=1 and ?m=0', () => {
    assert.equal(isForceMobileQuery({ m: '1' }), true)
    assert.equal(isForcePcQuery({ m: '0' }), true)
    assert.equal(isForceMobileQuery({ m: '0' }), false)
    assert.equal(isForcePcQuery({ m: '1' }), false)
    assert.equal(isForceMobileQuery({}), false)
  })
})
