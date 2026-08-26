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

// 全市场标的分页（含 listed，强制分页）
export function listInstrumentUniverse(query) {
  return request({
    url: '/market/instrument/universe',
    method: 'get',
    params: query
  })
}

// 行情台批量报价（最近两根日K，单次请求）
export function getBoardQuotes(query) {
  return request({
    url: '/market/board/quotes',
    method: 'get',
    params: query,
    timeout: 60000,
    loadingText: '加载中…'
  })
}

// 查询K线数据
export function getKline(query) {
  return request({
    url: '/market/kline',
    method: 'get',
    params: query,
    timeout: 12000
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

// AI行情研判：入队后立即返回 job ticket
export function aiAnalyze(data, options = {}) {
  return request({
    url: '/market/ai/analyze',
    method: 'post',
    data: data,
    timeout: 20000,
    loadingText: '研判中…',
    ...options
  })
}

export function getMarketJob(jobId) {
  return request({ url: '/market/jobs/' + jobId, method: 'get', timeout: 8000 })
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/** 轮询任务票直到 done/failed；间隔 2s，超时约 3 分钟。 */
export async function pollMarketJob(jobId, options = {}) {
  const intervalMs = options.intervalMs ?? 2000
  const timeoutMs = options.timeoutMs ?? 180000
  if (!jobId) return { status: 'failed', error: '缺少任务 ID' }
  const started = Date.now()
  for (;;) {
    const res = await getMarketJob(jobId)
    const ticket = res.data || {}
    const status = String(ticket.status || '')
    if (status === 'done' || status === 'failed') return ticket
    if (Date.now() - started >= timeoutMs) {
      return { ...ticket, status: 'failed', error: ticket.error || '任务等待超时' }
    }
    await sleep(intervalMs)
  }
}

// 标的详情概览（core | all）
export function getSymbolOverview(symbol, query) {
  return request({
    url: '/market/symbols/' + encodeURIComponent(symbol) + '/overview',
    method: 'get',
    params: query,
    timeout: (query && query.include === 'all') ? 120000 : 15000
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
    timeout: 20000,
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

export function getMarketWatchlistOverview(options = {}) {
  return request({
    url: '/market/watchlist/overview',
    method: 'get',
    timeout: options.timeout ?? 15000
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
    timeout: 30000
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

export function getStockPickMood() {
  return request({
    url: '/market/picks/mood',
    method: 'get'
  })
}

export function refreshStockPickMood() {
  return request({
    url: '/market/picks/mood/refresh',
    method: 'post'
  })
}

export function getStockPickLatest(query) {
  return request({
    url: '/market/picks/latest',
    method: 'get',
    params: query
  })
}

export function getStockPickDates(query) {
  return request({
    url: '/market/picks/dates',
    method: 'get',
    params: query
  })
}

export function runStockPick() {
  return request({
    url: '/market/picks/run',
    method: 'post',
    timeout: 180000,
    loadingText: '生成选股单…'
  })
}

export function collectMarketHeat(query) {
  return request({
    url: '/market/heat/collect',
    method: 'post',
    params: query
  })
}

// 盘中大盘指数：美股全时段返回；港股/A股仅当地盘中
export function getMarketIndexQuotes() {
  return request({
    url: '/market/index/quotes',
    method: 'get',
    timeout: 8000
  })
}

export function getMarketReviewLatest() {
  return request({
    url: '/market/review/latest',
    method: 'get'
  })
}

export function getMarketReviewHistory(query) {
  return request({
    url: '/market/review/history',
    method: 'get',
    params: query
  })
}

export function analyzeMarketReview(market) {
  return request({
    url: '/market/review/analyze',
    method: 'post',
    params: market ? { market } : {},
    timeout: 180000
  })
}
