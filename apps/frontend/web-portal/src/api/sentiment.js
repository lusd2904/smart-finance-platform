import request from '@/utils/request'

export function listNews(query) {
  return request({ url: '/sentiment/news/list', method: 'get', params: query, silent: true })
}

export function collectNews() {
  return request({ url: '/sentiment/news/collect', method: 'post', timeout: 120000 })
}

export function getStats() {
  return request({ url: '/sentiment/stats', method: 'get', silent: true })
}

export function listAnalysis(query) {
  return request({ url: '/sentiment/analysis/list', method: 'get', params: query, silent: true })
}

export function getTrend(limit) {
  return request({ url: '/sentiment/analysis/trend', method: 'get', params: { limit }, silent: true })
}

export function runAnalysis() {
  return request({ url: '/sentiment/analysis/run', method: 'post', timeout: 320000 })
}

export function getAnalysis(analysisId) {
  return request({ url: `/sentiment/analysis/${analysisId}`, method: 'get', silent: true })
}
