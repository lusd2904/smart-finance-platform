import request from '@/utils/request'

export function getTradeAccount() {
  return request({ url: '/trade/account', method: 'get', timeout: 30000 })
}

export function getTradeQuoteDepth(query) {
  return request({ url: '/trade/quote/depth', method: 'get', params: query, timeout: 30000 })
}

export function getTradeQuoteTrades(query) {
  return request({ url: '/trade/quote/trades', method: 'get', params: query, timeout: 30000 })
}

export function getTradeQuoteKline(query) {
  return request({ url: '/trade/quote/kline', method: 'get', params: query, timeout: 30000 })
}

export function getTradeQuoteSnapshot(query) {
  return request({ url: '/trade/quote/snapshot', method: 'get', params: query, timeout: 30000 })
}

export function getTradePositions() {
  return request({ url: '/trade/positions', method: 'get', timeout: 30000 })
}

export function getTradeOrders(scope = 'today') {
  return request({ url: '/trade/orders', method: 'get', params: { scope }, timeout: 30000 })
}

export function getTradeOrder(orderId) {
  return request({ url: '/trade/order/' + encodeURIComponent(orderId), method: 'get' })
}

export function submitTradeOrder(data) {
  return request({ url: '/trade/order', method: 'post', data, timeout: 60000 })
}

export function cancelTradeOrder(orderId) {
  return request({ url: '/trade/order/' + encodeURIComponent(orderId) + '/cancel', method: 'post' })
}

export function listNotifications(limit = 50) {
  return request({ url: '/trade/notifications', method: 'get', params: { limit } })
}

export function readNotifications(id) {
  return request({ url: '/trade/notifications/read', method: 'post', data: id ? { id } : {} })
}

export function runBacktest(data) {
  return request({ url: '/trade/backtest/run', method: 'post', data, timeout: 120000 })
}

export function listBacktests() {
  return request({ url: '/trade/backtest/list', method: 'get' })
}

export function getBacktest(runId) {
  return request({ url: '/trade/backtest/' + runId, method: 'get' })
}

export function listAiTradeRuns(limit = 30) {
  return request({ url: '/trade/ai-trade-runs', method: 'get', params: { limit } })
}

export function getAutoTradeStatus() {
  return request({ url: '/trade/auto/status', method: 'get' })
}

export function saveAutoTradeSettings(data) {
  return request({ url: '/trade/auto/settings', method: 'put', data })
}

export function runAutoTrade(data) {
  return request({ url: '/trade/auto/run', method: 'post', data, timeout: 180000 })
}

export function listAutoTradeDecisions(params) {
  return request({ url: '/trade/auto/decisions', method: 'get', params })
}

export function getHistoryCoverage() {
  return request({ url: '/trade/coverage', method: 'get', timeout: 120000 })
}
export function listStrategyProfiles() {
  return request({ url: '/trade/strategy-profiles', method: 'get' })
}
export function saveStrategyProfile(code, data) {
  return request({ url: '/trade/strategy-profiles/' + encodeURIComponent(code), method: 'put', data })
}
export function listRiskRules() {
  return request({ url: '/trade/risk/rules', method: 'get' })
}
export function saveRiskRule(data) {
  return request({ url: '/trade/risk/rules', method: 'post', data })
}
export function deleteRiskRule(ruleId) {
  return request({ url: '/trade/risk/rules/' + ruleId, method: 'delete' })
}
export function listRiskEvents(limit = 50, status) {
  return request({ url: '/trade/risk/events', method: 'get', params: { limit, status } })
}
export function updateRiskEventStatus(eventId, data) {
  return request({ url: '/trade/risk/events/' + eventId + '/status', method: 'put', data })
}
export function evaluateRisk() {
  return request({ url: '/trade/risk/evaluate', method: 'post', timeout: 60000 })
}
export function listNoticesDb(limit = 50) {
  return request({ url: '/trade/notices', method: 'get', params: { limit } })
}
export function readNoticesDb(id) {
  return request({ url: '/trade/notices/read', method: 'post', data: id ? { id } : {} })
}
export function runAiBatch(data, options = {}) {
  return request({ url: '/trade/ai/batch', method: 'post', data, timeout: 600000, loadingText: '研判中…', ...options })
}
export function listAiBatches() {
  return request({ url: '/trade/ai/batches', method: 'get' })
}
export function listAiBatchItems(batchId) {
  return request({ url: '/trade/ai/batches/' + batchId + '/items', method: 'get' })
}
export function getFeishuConfig() {
  return request({ url: '/trade/feishu/config', method: 'get' })
}
export function saveFeishuConfig(data) {
  return request({ url: '/trade/feishu/config', method: 'put', data })
}
export function testFeishuPush(data) {
  return request({ url: '/trade/feishu/test', method: 'post', data: data || {} })
}
