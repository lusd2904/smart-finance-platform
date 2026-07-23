import request from '@/utils/request'

export function getTradeAccount() {
  return request({ url: '/trade/account', method: 'get' })
}

export function getTradePositions() {
  return request({ url: '/trade/positions', method: 'get' })
}

export function getTradeOrders(scope = 'today') {
  return request({ url: '/trade/orders', method: 'get', params: { scope } })
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

export function listAiTradeRuns() {
  return request({ url: '/trade/ai-trade-runs', method: 'get' })
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
export function listRiskEvents(limit = 50) {
  return request({ url: '/trade/risk/events', method: 'get', params: { limit } })
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
export function runAiBatch(data) {
  return request({ url: '/trade/ai/batch', method: 'post', data, timeout: 600000 })
}
export function listAiBatches() {
  return request({ url: '/trade/ai/batches', method: 'get' })
}
export function listAiBatchItems(batchId) {
  return request({ url: '/trade/ai/batches/' + batchId + '/items', method: 'get' })
}
