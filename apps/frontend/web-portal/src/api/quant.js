import request from '@/utils/request'

export function getFactorSchema() {
  return request({ url: '/quant/factor/schema', method: 'get', silent: true })
}

export function listFactorSnapshots(limit = 80) {
  return request({ url: '/quant/factor/snapshots', method: 'get', params: { limit }, silent: true })
}

export function computeFactor(query) {
  return request({ url: '/quant/factor/compute', method: 'get', params: query, silent: true })
}

export function listStrategyHistory(query) {
  return request({ url: '/quant/strategy/history', method: 'get', params: query, silent: true })
}

export function runStrategy(data) {
  return request({ url: '/quant/strategy/run', method: 'post', data })
}

export function getLongbridgeConfig() {
  return request({ url: '/quant/longbridge/config', method: 'get', silent: true })
}

export function updateLongbridgeConfig(data) {
  return request({ url: '/quant/longbridge/config', method: 'put', data })
}

export function testLongbridge() {
  return request({ url: '/quant/longbridge/test', method: 'get' })
}

export function getReadmodelOverview() {
  return request({ url: '/quant/readmodel/overview', method: 'get', silent: true })
}
