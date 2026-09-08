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

export function getMarketReviewLatest() {
  return request({ url: '/market/review/latest', method: 'get', silent: true })
}

export function getLatestAi(symbol, query) {
  return request({
    url: `/market/symbols/${encodeURIComponent(symbol)}/ai/latest`,
    method: 'get',
    params: query,
    silent: true
  })
}
