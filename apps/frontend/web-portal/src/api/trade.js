import request from '@/utils/request'

export function getTradeAccount() {
  return request({ url: '/trade/account', method: 'get', timeout: 30000, silent: true })
}

export function getTradePositions() {
  return request({ url: '/trade/positions', method: 'get', timeout: 30000, silent: true })
}

export function getTradeOrders(scope = 'today') {
  return request({ url: '/trade/orders', method: 'get', params: { scope }, timeout: 30000, silent: true })
}

export function getTradeQuoteDepth(query) {
  return request({ url: '/trade/quote/depth', method: 'get', params: query, timeout: 30000, silent: true })
}

export function getTradeQuoteTrades(query) {
  return request({ url: '/trade/quote/trades', method: 'get', params: query, timeout: 30000, silent: true })
}

export function getTradeQuoteSnapshot(query) {
  return request({ url: '/trade/quote/snapshot', method: 'get', params: query, timeout: 30000, silent: true })
}

export function submitTradeOrder(data) {
  return request({ url: '/trade/order', method: 'post', data, timeout: 60000 })
}

export function cancelTradeOrder(orderId) {
  return request({ url: `/trade/order/${encodeURIComponent(orderId)}/cancel`, method: 'post' })
}

export function getAutoTradeStatus() {
  return request({ url: '/trade/auto/status', method: 'get', silent: true })
}

export function saveAutoTradeSettings(data) {
  return request({ url: '/trade/auto/settings', method: 'put', data })
}

export function listNotifications(limit = 50) {
  return request({ url: '/trade/notifications', method: 'get', params: { limit }, silent: true })
}

export function readNotifications(id) {
  return request({ url: '/trade/notifications/read', method: 'post', data: id ? { id } : {} })
}

export function getRiskTearsheet(query) {
  return request({ url: '/trade/risk/tearsheet', method: 'get', params: query, timeout: 30000, silent: true })
}

export function listRiskRules() {
  return request({ url: '/trade/risk/rules', method: 'get', silent: true })
}

export function saveRiskRule(data) {
  return request({ url: '/trade/risk/rules', method: 'post', data })
}

export function deleteRiskRule(ruleId) {
  return request({ url: `/trade/risk/rules/${ruleId}`, method: 'delete' })
}

export function listRiskEvents(limit = 50, status) {
  return request({ url: '/trade/risk/events', method: 'get', params: { limit, status }, silent: true })
}

export function updateRiskEventStatus(eventId, data) {
  return request({ url: `/trade/risk/events/${eventId}/status`, method: 'put', data })
}

export function evaluateRisk() {
  return request({ url: '/trade/risk/evaluate', method: 'post', timeout: 60000 })
}
