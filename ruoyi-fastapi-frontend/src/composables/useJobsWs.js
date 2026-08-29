/**
 * 分析任务 WS：Cookie + 开帧 {type:auth,token}，channel=jobs 推送总览。
 * 断线由调用方启动 HTTP 轮询回退（对照行情 hub REST 60s）。
 */
import { getToken } from '@/utils/auth'
import { buildJobsWsUrl, parseJobsWsMessage } from '@/composables/jobsWsCore'

export { buildJobsWsUrl, parseJobsWsMessage }

export function jobsWsUrl(intervalSec = 5) {
  const env = typeof import.meta !== 'undefined' ? import.meta.env : undefined
  return buildJobsWsUrl({
    apiBase: (env && env.VITE_APP_BASE_API) || '/docker-api',
    protocol: typeof location !== 'undefined' ? location.protocol : 'http:',
    host: typeof location !== 'undefined' ? location.host : 'localhost',
    intervalSec,
  })
}

export function bindJobsSocket({ onData, onUp, onDown, intervalSec = 5 } = {}) {
  let ws = null
  let retryTimer = null
  let closed = true
  let attempt = 0

  function sendAuth() {
    const token = getToken()
    if (token && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'auth', token }))
    }
  }

  function emitJobs(data) {
    if (!data || typeof onData !== 'function') return
    try {
      onData(data)
    } catch {
      /* listener 异常不影响通道 */
    }
  }

  function scheduleRetry() {
    if (closed) return
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    const delay = Math.min(30000, 2000 * 2 ** Math.min(attempt, 4))
    attempt += 1
    retryTimer = setTimeout(connect, delay)
  }

  function connect() {
    if (closed) return
    try {
      ws = new WebSocket(jobsWsUrl(intervalSec))
    } catch {
      if (typeof onDown === 'function') onDown()
      scheduleRetry()
      return
    }
    ws.onopen = () => {
      attempt = 0
      sendAuth()
      if (typeof onUp === 'function') onUp()
    }
    ws.onmessage = (ev) => {
      const parsed = parseJobsWsMessage(ev.data)
      if (parsed.kind === 'jobs') emitJobs(parsed.data)
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      ws = null
      if (closed) return
      if (typeof onDown === 'function') onDown()
      scheduleRetry()
    }
  }

  return {
    start() {
      if (!closed) return
      closed = false
      attempt = 0
      connect()
    },
    stop() {
      closed = true
      if (retryTimer) {
        clearTimeout(retryTimer)
        retryTimer = null
      }
      if (ws) {
        ws.onclose = null
        ws.close()
        ws = null
      }
    },
  }
}
