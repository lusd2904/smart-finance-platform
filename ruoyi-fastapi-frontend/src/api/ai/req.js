import request from '@/utils/request'

export function getReqRoom() {
  return request({ url: '/ai/req/room', method: 'get' })
}

export function getReqMessages(query) {
  return request({ url: '/ai/req/messages', method: 'get', params: query })
}

export function sendReqMessage(data) {
  return request({ url: '/ai/req/messages', method: 'post', data, timeout: 180000 })
}

export function summarizeReq() {
  return request({ url: '/ai/req/summarize', method: 'post', timeout: 180000 })
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
