import request from '@/utils/request'

// 查询资讯分页列表
export function listNews(query) {
  return request({
    url: '/sentiment/news/list',
    method: 'get',
    params: query
  })
}

// 删除资讯
export function delNews(newsIds) {
  return request({
    url: '/sentiment/news/' + newsIds,
    method: 'delete'
  })
}

// 手动触发采集
export function collectNews() {
  return request({
    url: '/sentiment/news/collect',
    method: 'post',
    timeout: 120000
  })
}

// 查询舆情统计
export function getStats() {
  return request({
    url: '/sentiment/stats',
    method: 'get'
  })
}

// 查询分析结果分页列表
export function listAnalysis(query) {
  return request({
    url: '/sentiment/analysis/list',
    method: 'get',
    params: query
  })
}

// 查询分析趋势
export function getTrend(limit) {
  return request({
    url: '/sentiment/analysis/trend',
    method: 'get',
    params: { limit: limit }
  })
}

// 手动触发AI分析（模型调用约 47–90s，单独加长超时，避免前端误报超时）
export function runAnalysis() {
  return request({
    url: '/sentiment/analysis/run',
    method: 'post',
    timeout: 320000,
    loadingText: '分析中…'
  })
}

// 查询分析详情
export function getAnalysis(analysisId) {
  return request({
    url: '/sentiment/analysis/' + analysisId,
    method: 'get'
  })
}

// 查询AI配置
export function getConfig() {
  return request({
    url: '/sentiment/config',
    method: 'get'
  })
}

// 保存AI配置
export function updateConfig(data) {
  return request({
    url: '/sentiment/config',
    method: 'put',
    data: data
  })
}
