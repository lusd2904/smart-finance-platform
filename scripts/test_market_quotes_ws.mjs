import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyQuotePatch,
  buildMarketQuotesWsUrl,
  normalizeSubscribePairs,
  parseQuotesWsMessage,
} from '../ruoyi-fastapi-frontend/src/composables/marketQuotesWsCore.js'
import { pickPollDelay } from '../ruoyi-fastapi-frontend/src/composables/useAdaptivePoll.js'
import { buildJobsWsUrl, parseJobsWsMessage } from '../ruoyi-fastapi-frontend/src/composables/jobsWsCore.js'

describe('market quotes ws url', () => {
  it('uses relative docker-api on same host', () => {
    const url = buildMarketQuotesWsUrl({
      apiBase: '/docker-api',
      protocol: 'http:',
      host: '127.0.0.1:12580',
    })
    assert.equal(url, 'ws://127.0.0.1:12580/docker-api/ws/market/quotes?interval=15')
    assert.equal(url.includes('token='), false)
  })

  it('upgrades absolute https api base', () => {
    const url = buildMarketQuotesWsUrl({
      apiBase: 'https://sfp.example/docker-api',
      protocol: 'http:',
      host: 'unused',
    })
    assert.equal(url, 'https://sfp.example/docker-api/ws/market/quotes?interval=15'.replace('https', 'wss'))
  })

  it('splits index and quotes channels', () => {
    const indexMsg = parseQuotesWsMessage(JSON.stringify({
      channel: 'index',
      data: { items: [{ symbol: 'usIXIC', last: 1 }] },
    }))
    assert.equal(indexMsg.kind, 'index')
    const quotesMsg = parseQuotesWsMessage(JSON.stringify({
      channel: 'quotes',
      quotes: { items: [{ symbol: 'AAPL', last: 2 }] },
    }))
    assert.equal(quotesMsg.kind, 'quotes')
    assert.equal(quotesMsg.data.items[0].symbol, 'AAPL')
  })

  it('patches watchlist last from live items', () => {
    const rows = applyQuotePatch(
      [{ symbol: 'AAPL', market: 'US', last: 1, name: 'Apple' }],
      [{ symbol: 'AAPL', market: 'US', last: 227.5, changePct: 1.2 }],
    )
    assert.equal(rows[0].last, 227.5)
    assert.equal(rows[0].changeRate, 1.2)
    assert.equal(rows[0].quoteSource, 'live')
  })

  it('normalizes subscribe pairs and caps at 80', () => {
    const pairs = normalizeSubscribePairs(['AAPL:US', { symbol: '00700', market: 'HK' }, 'AAPL.US'])
    assert.deepEqual(pairs, [{ symbol: 'AAPL', market: 'US' }, { symbol: '00700', market: 'HK' }])
    assert.equal(normalizeSubscribePairs(Array.from({ length: 120 }, (_, i) => `S${i}`)).length, 80)
  })
})

describe('adaptive poll delay', () => {
  it('picks busy vs idle milliseconds', () => {
    assert.equal(pickPollDelay(true, 5000, 30000), 5000)
    assert.equal(pickPollDelay(false, 8000, 45000), 45000)
    assert.equal(pickPollDelay(true), 3000)
    assert.equal(pickPollDelay(false), 30000)
  })
})

describe('jobs ws url and payload', () => {
  it('builds /ws/jobs without query token', () => {
    const url = buildJobsWsUrl({
      apiBase: '/docker-api',
      protocol: 'http:',
      host: '127.0.0.1:12580',
      intervalSec: 5,
    })
    assert.equal(url, 'ws://127.0.0.1:12580/docker-api/ws/jobs?interval=5')
  })

  it('parses channel=jobs overview', () => {
    const parsed = parseJobsWsMessage(JSON.stringify({
      channel: 'jobs',
      data: { schedulerAlive: true, jobs: [] },
    }))
    assert.equal(parsed.kind, 'jobs')
    assert.equal(parsed.data.schedulerAlive, true)
  })
})
