/**
 * 行情 WS 单例：登录壳共用一条连接（对照 Open-Terminal / profitmaker）。
 * 指数默认推送；自选/交易台 {type:subscribe} 后再推个股最新价。
 */
import { getMarketIndexQuotes } from '@/api/market'
import { getToken } from '@/utils/auth'
import {
  buildMarketQuotesWsUrl,
  normalizeSubscribePairs,
  parseQuotesWsMessage,
} from '@/composables/marketQuotesWsCore'

export {
  applyQuotePatch,
  buildMarketQuotesWsUrl,
  normalizeSubscribePairs,
  parseQuotesWsMessage,
} from '@/composables/marketQuotesWsCore'

export function marketQuotesWsUrl(intervalSec = 15) {
  return buildMarketQuotesWsUrl({
    apiBase: import.meta.env.VITE_APP_BASE_API || '/docker-api',
    protocol: location.protocol,
    host: location.host,
    intervalSec,
  })
}

function createQuotesHub({ intervalSec = 15 } = {}) {
  const indexListeners = new Set()
  const quoteSubs = new Map()
  let seq = 0
  let ws = null
  let pollTimer = null
  let retryTimer = null
  let closed = true
  let attempt = 0
  let lastIndex = null
  let lastQuotes = null

  function mergedPairs() {
    const all = []
    for (const sub of quoteSubs.values()) all.push(...sub.pairs)
    return normalizeSubscribePairs(all)
  }

  function emitIndex(data) {
    lastIndex = data
    for (const cb of indexListeners) {
      try {
        cb(data)
      } catch {
        /* listener 异常不影响通道 */
      }
    }
  }

  function emitQuotes(data) {
    lastQuotes = data
    const items = (data && data.items) || []
    for (const sub of quoteSubs.values()) {
      try {
        sub.cb({ items })
      } catch {
        /* listener 异常不影响通道 */
      }
    }
  }

  function sendJson(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload))
    }
  }

  function sendSubscribe() {
    sendJson({ type: 'subscribe', symbols: mergedPairs() })
  }

  async function loadRest() {
    try {
      const res = await getMarketIndexQuotes()
      emitIndex(res.data || {})
    } catch {
      /* 保留上次快照 */
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
    pollTimer = setInterval(loadRest, 60000)
  }

  function connect() {
    if (closed) return
    try {
      ws = new WebSocket(marketQuotesWsUrl(intervalSec))
    } catch {
      startPoll()
      return
    }
    ws.onopen = () => {
      attempt = 0
      stopPoll()
      const token = getToken()
      if (token && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'auth', token }))
      }
      sendSubscribe()
    }
    ws.onmessage = (ev) => {
      const parsed = parseQuotesWsMessage(ev.data)
      if (parsed.kind === 'index') emitIndex(parsed.data)
      else if (parsed.kind === 'quotes') emitQuotes(parsed.data)
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

  function ensureStarted() {
    if (!closed) return
    closed = false
    loadRest()
    connect()
  }

  function maybeStop() {
    if (indexListeners.size || quoteSubs.size) return
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
  }

  return {
    subscribeIndex(cb) {
      if (typeof cb !== 'function') return () => {}
      ensureStarted()
      indexListeners.add(cb)
      if (lastIndex) cb(lastIndex)
      return () => {
        indexListeners.delete(cb)
        maybeStop()
      }
    },
    subscribeQuotes(pairs, cb) {
      if (typeof cb !== 'function') return () => {}
      ensureStarted()
      const id = ++seq
      quoteSubs.set(id, { pairs: normalizeSubscribePairs(pairs), cb })
      sendSubscribe()
      if (lastQuotes) cb({ items: lastQuotes.items || [] })
      return () => {
        quoteSubs.delete(id)
        sendSubscribe()
        maybeStop()
      }
    },
    reloadIndex: loadRest,
  }
}

let hubSingleton = null

export function getQuotesHub(opts) {
  if (!hubSingleton) hubSingleton = createQuotesHub(opts)
  return hubSingleton
}

/** 兼容旧调用：每页 bind 实际复用单例，只多一个指数监听。 */
export function bindMarketQuotesSocket({ onData, intervalSec = 15 } = {}) {
  const hub = getQuotesHub({ intervalSec })
  let unsub = null
  return {
    start() {
      if (unsub) unsub()
      unsub = hub.subscribeIndex(onData)
    },
    stop() {
      if (unsub) {
        unsub()
        unsub = null
      }
    },
    reload: () => hub.reloadIndex(),
  }
}
