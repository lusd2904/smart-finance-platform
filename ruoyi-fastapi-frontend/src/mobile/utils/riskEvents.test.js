import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseRiskEvents, sentimentIndexTo100, sentimentDirection } from './riskEvents.js'

describe('parseRiskEvents', () => {
  it('accepts arrays', () => {
    assert.deepEqual(parseRiskEvents(['a', 'b']), ['a', 'b'])
  })

  it('parses JSON string like Flutter', () => {
    assert.deepEqual(parseRiskEvents('["地缘","利率"]'), ['地缘', '利率'])
  })

  it('splits newline / semicolon text', () => {
    assert.deepEqual(parseRiskEvents('地缘；利率\n通胀'), ['地缘', '利率', '通胀'])
  })

  it('returns empty for null / blank', () => {
    assert.deepEqual(parseRiskEvents(null), [])
    assert.deepEqual(parseRiskEvents(''), [])
  })
})

describe('sentimentIndexTo100', () => {
  it('maps [-10,10] linearly and leaves percent as-is', () => {
    assert.equal(sentimentIndexTo100(-10), 0)
    assert.equal(sentimentIndexTo100(0), 50)
    assert.equal(sentimentIndexTo100(10), 100)
    assert.equal(sentimentIndexTo100(80), 80)
  })
})

describe('sentimentDirection', () => {
  it('normalizes bull / bear tokens', () => {
    assert.equal(sentimentDirection('利多'), 'up')
    assert.equal(sentimentDirection('买入'), 'up')
    assert.equal(sentimentDirection('bearish'), 'down')
    assert.equal(sentimentDirection('减持'), 'down')
    assert.equal(sentimentDirection('中性'), 'flat')
  })
})
