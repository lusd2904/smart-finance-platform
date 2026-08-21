import request from '@/utils/request'

// 查询标的列表（可选按分类过滤）
export function listInstrument(categoryOrQuery) {
  const params = typeof categoryOrQuery === 'string' || categoryOrQuery == null
    ? { category: categoryOrQuery }
    : categoryOrQuery
  return request({
    url: '/market/instrument/list',
    method: 'get',
    params
  })
}

// 行情台批量报价（最近两根日K，单次请求）
export function getBoardQuotes(query) {
  return request({
    url: '/market/board/quotes',
    method: 'get',
    params: query,
    timeout: 8000,
    loadingText: '加载中…'
  })
}

// 查询K线数据
export function getKline(query) {
  return request({
    url: '/market/kline',
    method: 'get',
    params: query
  })
}

// 查询技术指标序列
export function getIndicators(query) {
  return request({
    url: '/market/indicators',
    method: 'get',
    params: query
  })
}

// 手动同步行情数据
export function syncMarket(data) {
  return request({
    url: '/market/sync',
    method: 'post',
    data: data
  })
}

// AI行情研判（模型调用约 47–90s，需长于默认超时）
export function aiAnalyze(data, options = {}) {
  return request({
    url: '/market/ai/analyze',
    method: 'post',
    data: data,
    timeout: 120000,
    loadingText: '研判中…',
    ...options
  })
}

// 标的详情概览（core | all）
export function getSymbolOverview(symbol, query) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/overview',
    method: 'get',
    params: query
  })
}

// 标的历史K线
export function getSymbolHistory(symbol, query) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/history',
    method: 'get',
    params: query
  })
}

// 标的公告/资讯/讨论
export function getSymbolContent(symbol, query) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/content',
    method: 'get',
    params: query
  })
}

// 触发标的AI研判
export function symbolAiAnalyze(symbol, query, options = {}) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/ai-analyze',
    method: 'post',
    params: query,
    timeout: 120000,
    loadingText: '研判中…',
    ...options
  })
}

// 最新AI研判
export function getLatestAi(symbol, query) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/ai/latest',
    method: 'get',
    params: query
  })
}

// 财经资讯简报流
export function getFinanceBriefings(query) {
  return request({
    url: '/market/finance/briefings',
    method: 'get',
    params: query
  })
}

export function getMarketWatchlistOverview() {
  return request({
    url: '/market/watchlist/overview',
    method: 'get'
  })
}

export function listMarketWatchlist(query) {
  return request({
    url: '/market/watchlist/list',
    method: 'get',
    params: query
  })
}

export function addMarketWatchlist(data) {
  return request({
    url: '/market/watchlist',
    method: 'post',
    data
  })
}

export function delMarketWatchlist(ids) {
  return request({
    url: '/market/watchlist/' + ids,
    method: 'delete'
  })
}

export function analyzeMarketWatchlist(data) {
  return request({
    url: '/market/watchlist/analyze',
    method: 'post',
    data: data || {},
    timeout: 180000
  })
}

export function getMarketWatchlistAnalysis(query) {
  return request({
    url: '/market/watchlist/analysis',
    method: 'get',
    params: query
  })
}

export function getMarketWatchlistBacktest(query) {
  return request({
    url: '/market/watchlist/backtest',
    method: 'get',
    params: query
  })
}

export function getMarketHeatDaily(query) {
  return request({
    url: '/market/heat/daily',
    method: 'get',
    params: query
  })
}

export function getMarketHeatTrend(query) {
  return request({
    url: '/market/heat/trend',
    method: 'get',
    params: query
  })
}

export function getMarketHeatDates(query) {
  return request({
    url: '/market/heat/dates',
    method: 'get',
    params: query
  })
}

export function getMarketHeatConfig() {
  return request({
    url: '/market/heat/config',
    method: 'get'
  })
}

export function collectMarketHeat(query) {
  return request({
    url: '/market/heat/collect',
    method: 'post',
    params: query
  })
}
