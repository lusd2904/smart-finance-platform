import request from '@/utils/request'

export function getReqRoom() {
  return request({ url: '/ai/req/room', method: 'get' })
}

export function getReqMessages(query) {
  return request({ url: '/ai/req/messages', method: 'get', params: query })
}

export function sendReqMessage(data) {
  return request({ url: '/ai/req/messages', method: 'post', data })
}

export function summarizeReq() {
  return request({ url: '/ai/req/summarize', method: 'post' })
}

export function getReqJob(jobId) {
  return request({ url: '/ai/req/jobs/' + jobId, method: 'get' })
}

export function listReqItems(status) {
  return request({ url: '/ai/req/items', method: 'get', params: status ? { status } : {} })
}

export function updateReqStatus(itemId, data) {
  return request({ url: '/ai/req/items/' + itemId + '/status', method: 'put', data })
}

export function exportReqItems(status) {
  return request({ url: '/ai/req/items/export', method: 'get', params: status ? { status } : {} })
}

export function listReqBots() {
  return request({ url: '/ai/req/bots', method: 'get' })
}

export function saveReqBots(data) {
  return request({ url: '/ai/req/bots', method: 'put', data })
}
