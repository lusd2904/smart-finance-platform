import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { pickPollDelay } from '../ruoyi-fastapi-frontend/src/composables/useAdaptivePoll.js'
import { buildJobsWsUrl, parseJobsWsMessage } from '../ruoyi-fastapi-frontend/src/composables/jobsWsCore.js'

describe('adaptive poll delay', () => {
  it('picks busy vs idle milliseconds', () => {
    assert.equal(pickPollDelay(true, 5000, 30000), 5000)
    assert.equal(pickPollDelay(false, 5000, 30000), 30000)
    assert.equal(pickPollDelay(true), 3000)
    assert.equal(pickPollDelay(false), 30000)
    assert.equal(pickPollDelay(1, 8000, 45000), 8000)
    assert.equal(pickPollDelay(0, 8000, 45000), 45000)
  })
})

describe('jobs ws url and payload', () => {
  it('builds /ws/jobs on same host', () => {
    const url = buildJobsWsUrl({
      apiBase: '/docker-api',
      protocol: 'http:',
      host: '127.0.0.1:12580',
      intervalSec: 5,
    })
    assert.equal(url, 'ws://127.0.0.1:12580/docker-api/ws/jobs?interval=5')
    assert.equal(url.includes('token='), false)
  })

  it('applies channel=jobs overview', () => {
    const parsed = parseJobsWsMessage(JSON.stringify({
      channel: 'jobs',
      data: { schedulerAlive: true, queueDepth: 2, jobs: [{ jobId: 1 }] },
    }))
    assert.equal(parsed.kind, 'jobs')
    assert.equal(parsed.data.schedulerAlive, true)
    assert.equal(parsed.data.queueDepth, 2)
    assert.equal(parsed.data.jobs[0].jobId, 1)
  })
})
