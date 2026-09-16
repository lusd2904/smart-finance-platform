import { getMarketIndexQuotes } from '@/api/market'
import { getToken } from '@/utils/auth'
import { unwrap, unwrapList } from '@/utils/list'

export function buildMarketQuotesWsUrl(intervalSec = 15) {
  const clamped = Math.max(3, Math.min(60, Number(intervalSec) || 15))
  const base = import.meta.env.VITE_APP_BASE_API || '/dev-api'
  const suffix = `/ws/market/quotes?interval=${clamped}`
  if (/^https?:\/\//i.test(base)) {
    const u = new URL(`${String(base).replace(/\/$/, '')}${suffix}`)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    return u.toString()
  }
  const proto = typeof location !== 'undefined' && location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = typeof location !== 'undefined' ? location.host : 'localhost'
  return `${proto}//${host}${String(base).replace(/\/$/, '')}${suffix}`
}

function itemsFrom(payload) {
  const raw = unwrap(payload)
  const items = raw.items || raw.list || (Array.isArray(raw) ? raw : unwrapList(payload))
  return Array.isArray(items) ? items : []
}

/** Same contract as ruoyi bindMarketQuotesSocket: start / stop / reload. WS first, REST poll fallback. */
export function bindMarketQuotesSocket({ onData, intervalSec = 15 } = {}) {
  let ws = null
  let pollTimer = null
  let retryTimer = null
  let closed = true
  let attempt = 0

  async function loadRest() {
    try {
      const items = itemsFrom(await getMarketIndexQuotes())
      if (items.length && typeof onData === 'function') onData({ items })
    } catch {
      /* keep last snapshot */
    }
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startPoll() {
    stopPoll()
    pollTimer = setInterval(loadRest, Math.max(3000, (Number(intervalSec) || 15) * 1000))
  }

  function connect() {
    if (closed) return
    try {
      ws = new WebSocket(buildMarketQuotesWsUrl(intervalSec))
    } catch {
      startPoll()
      return
    }
    ws.onopen = () => {
      attempt = 0
      stopPoll()
      const token = getToken()
      if (token && token !== 'demo-stub-token' && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'auth', token }))
      }
    }
    ws.onmessage = (ev) => {
      if (ev.data === 'ping' || ev.data === 'pong') return
      let msg
      try {
        msg = typeof ev.data === 'string' ? JSON.parse(ev.data) : ev.data
      } catch {
        return
      }
      const data = msg?.data || msg
      const items = data?.items || data?.list
      if (Array.isArray(items) && items.length && typeof onData === 'function') onData({ items })
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      ws = null
      if (closed) return
      startPoll()
      const delay = Math.min(30000, 2000 * 2 ** Math.min(attempt, 4))
      attempt += 1
      retryTimer = setTimeout(connect, delay)
    }
  }

  return {
    start() {
      if (!closed) return
      closed = false
      loadRest()
      connect()
    },
    stop() {
      closed = true
      stopPoll()
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
    reload: loadRest
  }
}
