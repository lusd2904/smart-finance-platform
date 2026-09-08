import request from '@/utils/request'

export function getMarketIndexQuotes() {
  return request({ url: '/market/index/quotes', method: 'get', timeout: 8000, silent: true })
}

export function getMarketWatchlistOverview() {
  return request({ url: '/market/watchlist/overview', method: 'get', timeout: 15000, silent: true })
}

export function listMarketWatchlist(query) {
  return request({ url: '/market/watchlist/list', method: 'get', params: query, silent: true })
}

export function getKline(query) {
  return request({ url: '/market/kline', method: 'get', params: query, timeout: 12000, silent: true })
}

export function getSymbolOverview(symbol, query) {
  return request({
    url: `/market/symbols/${encodeURIComponent(symbol)}/overview`,
    method: 'get',
    params: query,
    timeout: 15000,
    silent: true
  })
}

export function getSymbolContent(symbol, query) {
  return request({
    url: `/market/symbols/${encodeURIComponent(symbol)}/content`,
    method: 'get',
    params: query,
    silent: true
  })
}

export function listInstrumentUniverse(query) {
  return request({ url: '/market/instrument/universe', method: 'get', params: query, silent: true })
}

export function getBoardQuotes(query) {
  return request({ url: '/market/board/quotes', method: 'get', params: query, timeout: 60000, silent: true })
}

export function addMarketWatchlist(data) {
  return request({ url: '/market/watchlist', method: 'post', data })
}

export function delMarketWatchlist(ids) {
  return request({ url: `/market/watchlist/${ids}`, method: 'delete' })
}

export function getMarketWatchlistAnalysis(query) {
  return request({ url: '/market/watchlist/analysis', method: 'get', params: query, silent: true })
}

export function getMarketWatchlistBacktest(query) {
  return request({ url: '/market/watchlist/backtest', method: 'get', params: query, silent: true })
}

export function analyzeMarketWatchlist(data) {
  return request({ url: '/market/watchlist/analyze', method: 'post', data: data || {}, timeout: 30000 })
}

export function getWatchlistCorrelation(query) {
  return request({ url: '/market/watchlist/correlation', method: 'get', params: query, timeout: 30000, silent: true })
}

export function getMarketFlowBoard(query) {
  return request({ url: '/market/flow/board', method: 'get', params: query, timeout: 20000, silent: true })
}

export function getMarketHeatDaily(query) {
  return request({ url: '/market/heat/daily', method: 'get', params: query, silent: true })
}

export function getMarketHeatTrend(query) {
  return request({ url: '/market/heat/trend', method: 'get', params: query, silent: true })
}

export function getMarketHeatDates(query) {
  return request({ url: '/market/heat/dates', method: 'get', params: query, silent: true })
}

export function getFinanceBriefings(query) {
  return request({ url: '/market/finance/briefings', method: 'get', params: query, silent: true })
}

export function getStockPickMood() {
  return request({ url: '/market/picks/mood', method: 'get', timeout: 20000, silent: true })
}

export function refreshStockPickMood() {
  return request({ url: '/market/picks/mood/refresh', method: 'post', timeout: 15000 })
}

export function getLiveQuotes(symbols) {
  const list = Array.isArray(symbols) ? symbols : [symbols]
  return request({
    url: '/market/quotes/live',
    method: 'get',
    params: { symbols: list.filter(Boolean).join(',') },
    timeout: 8000,
    silent: true
  })
}

export function getStockPickLatest(query) {
  return request({ url: '/market/picks/latest', method: 'get', params: query, timeout: 30000, silent: true })
}

export function getStockPickDates(query) {
  return request({ url: '/market/picks/dates', method: 'get', params: query, silent: true })
}

export function runStockPick() {
  return request({ url: '/market/picks/run', method: 'post', timeout: 180000 })
}

export function getMarketReviewLatest() {
  return request({ url: '/market/review/latest', method: 'get', silent: true })
}

export function getMarketReviewHistory(query) {
  return request({ url: '/market/review/history', method: 'get', params: query, silent: true })
}

export function analyzeMarketReview(market) {
  return request({ url: '/market/review/analyze', method: 'post', params: market ? { market } : {}, timeout: 20000 })
}

export function getLatestAi(symbol, query) {
  return request({
    url: `/market/symbols/${encodeURIComponent(symbol)}/ai/latest`,
    method: 'get',
    params: query,
    silent: true
  })
}
