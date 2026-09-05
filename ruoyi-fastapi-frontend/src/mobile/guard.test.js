import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  FORCE_MOBILE_COOKIE,
  isForceMobileQuery,
  isForcePcQuery,
  isMobilePath,
  parseMFlag,
  persistShellForce,
  readShellForce,
  shellForceRedirect
} from './guard.js'

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

describe('readShellForce / persistShellForce', () => {
  it('lets the query win and writes sfp_m for later visits', () => {
    const store = { sfp_m: '0' }
    const jar = {
      get: (k) => store[k],
      set: (k, v, opts) => {
        store[k] = v
        jar.lastOpts = opts
      }
    }
    assert.equal(readShellForce({ m: '1' }, jar), 1)
    assert.equal(readShellForce({}, jar), 0)
    persistShellForce(1, jar)
    assert.equal(store[FORCE_MOBILE_COOKIE], '1')
    assert.equal(jar.lastOpts.path, '/')
    assert.equal(readShellForce({}, jar), 1)
    persistShellForce(0, jar)
    assert.equal(readShellForce({ m: '1' }, jar), 1)
    assert.equal(readShellForce({}, jar), 0)
  })
})

describe('shellForceRedirect', () => {
  it('forces /m for m=1 and PC for m=0', () => {
    assert.equal(shellForceRedirect('/login', 1, false), '/m/login')
    assert.equal(shellForceRedirect('/portal', 1, true), '/m')
    assert.equal(shellForceRedirect('/m', 1, false), null)
    assert.equal(shellForceRedirect('/m/picks', 0, false), '/login')
    assert.equal(shellForceRedirect('/m', 0, true), '/portal')
    assert.equal(shellForceRedirect('/login', 0, false), null)
    assert.equal(shellForceRedirect('/m', null, false), null)
  })
})
