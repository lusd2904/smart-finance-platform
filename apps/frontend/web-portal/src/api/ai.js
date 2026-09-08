import request from '@/utils/request'

export function listModel(query) {
  return request({ url: '/ai/model/list', method: 'get', params: query, silent: true })
}

export function listModelAll() {
  return request({ url: '/ai/model/all', method: 'get', silent: true })
}

export function listChatSession() {
  return request({ url: '/ai/chat/session/list', method: 'get', silent: true })
}

export function getChatSession(sessionId) {
  return request({ url: `/ai/chat/session/${sessionId}`, method: 'get', silent: true })
}

export function analyzeOneshot(data) {
  return request({ url: '/ai/chat/oneshot', method: 'post', data, timeout: 120000 })
}
