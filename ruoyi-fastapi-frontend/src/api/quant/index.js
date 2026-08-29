import request from '@/utils/request'

// 查询7大因子族定义
export function getReadmodelOverview() {
  return request({
    url: '/quant/readmodel/overview',
    method: 'get'
  })
}

export function getFactorSchema() {
  return request({
    url: '/quant/factor/schema',
    method: 'get'
  })
}

// 计算标的因子值与打分
export function computeFactor(query) {
  return request({
    url: '/quant/factor/compute',
    method: 'get',
    params: query
  })
}

export function listFactorSnapshots(limit = 80) {
  return request({
    url: '/quant/factor/snapshots',
    method: 'get',
    params: { limit }
  })
}

export function exportFactorSnapshots() {
  return request({
    url: '/quant/factor/snapshots/export',
    method: 'get',
    responseType: 'blob'
  })
}

export function runDailyFactorScan(profile = 'balanced') {
  return request({
    url: '/quant/scan/daily',
    method: 'post',
    params: { profile },
    timeout: 20000
  })
}

export function runIndicatorRefresh() {
  return request({
    url: '/quant/scan/indicators',
    method: 'post',
    timeout: 60000
  })
}

export function getFactorQc(market = 'US') {
  return request({
    url: '/quant/factor/qc',
    method: 'get',
    params: { market }
  })
}

export function runFactorQc(market = 'US') {
  return request({
    url: '/quant/factor/qc/run',
    method: 'post',
    params: { market },
    timeout: 20000
  })
}

// 查询自选池列表
export function listWatchlist(query) {
  return request({
    url: '/quant/watchlist/list',
    method: 'get',
    params: query
  })
}

// 新增自选
export function addWatchlist(data) {
  return request({
    url: '/quant/watchlist',
    method: 'post',
    data: data
  })
}

// 删除自选
export function delWatchlist(ids) {
  return request({
    url: '/quant/watchlist/' + ids,
    method: 'delete'
  })
}

// 运行策略
export function runStrategy(data) {
  return request({
    url: '/quant/strategy/run',
    method: 'post',
    data: data
  })
}

// 查询策略运行历史（分页）
export function listStrategyHistory(query) {
  return request({
    url: '/quant/strategy/history',
    method: 'get',
    params: query
  })
}

// 扫描运行台账列表
export function listScanRuns(query) {
  return request({
    url: '/quant/scan-runs',
    method: 'get',
    params: query
  })
}

// 扫描运行详情
export function getScanRunDetail(cycleId) {
  return request({
    url: '/quant/scan-runs/' + encodeURIComponent(cycleId),
    method: 'get'
  })
}

// 标的最新扫描+AI
export function getSymbolLatestScan(symbol, query) {
  return request({
    url: '/quant/symbols/' + encodeURIComponent(symbol) + '/latest',
    method: 'get',
    params: query
  })
}

// 测试长桥连接
export function testLongbridge() {
  return request({
    url: '/quant/longbridge/test',
    method: 'get'
  })
}

// 查询长桥配置
export function getLongbridgeConfig() {
  return request({
    url: '/quant/longbridge/config',
    method: 'get'
  })
}

// 保存长桥配置
export function updateLongbridgeConfig(data) {
  return request({
    url: '/quant/longbridge/config',
    method: 'put',
    data: data
  })
}

export function getDailyList() {
  return request({ url: '/quant/daily-list', method: 'get' })
}

export function scanDailyList(data) {
  return request({ url: '/quant/daily-list/scan', method: 'post', data: data || {} })
}

export function openDailyList(data) {
  return request({ url: '/quant/daily-list/open', method: 'post', data })
}

export function setDailyListAuto(data) {
  return request({ url: '/quant/daily-list/auto', method: 'post', data })
}
