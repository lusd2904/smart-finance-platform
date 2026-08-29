/**
 * 分析任务 WS 纯函数：URL 与 channel=jobs 载荷。
 */
import { buildMarketQuotesWsUrl } from './marketQuotesWsCore.js'

export function buildJobsWsUrl({ apiBase, protocol, host, intervalSec = 5 } = {}) {
  return buildMarketQuotesWsUrl({ apiBase, protocol, host, intervalSec }).replace(
    '/ws/market/quotes',
    '/ws/jobs'
  )
}

export function parseJobsWsMessage(raw) {
  if (raw === 'ping' || raw === 'pong') return { kind: 'heartbeat', raw }
  let msg
  try {
    msg = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return { kind: 'raw', raw }
  }
  if (!msg || typeof msg !== 'object') return { kind: 'raw', raw }
  if (msg.channel === 'jobs') {
    const data = msg.data != null ? msg.data : msg.overview != null ? msg.overview : msg
    return { kind: 'jobs', data }
  }
  return { kind: 'other', data: msg }
}
