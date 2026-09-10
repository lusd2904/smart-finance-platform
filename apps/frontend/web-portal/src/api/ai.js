import request from '@/utils/request'

export function listModel(query) {
  return request({ url: '/ai/model/list', method: 'get', params: query, silent: true })
}

export function listModelAll() {
  return request({ url: '/ai/model/all', method: 'get', silent: true })
}

export function getModel(modelId) {
  return request({ url: `/ai/model/${modelId}`, method: 'get', silent: true })
}

export function addModel(data) {
  return request({ url: '/ai/model', method: 'post', data })
}

export function updateModel(data) {
  return request({ url: '/ai/model', method: 'put', data })
}

export function delModel(modelId) {
  return request({ url: `/ai/model/${modelId}`, method: 'delete' })
}

export function listChatSession() {
  return request({ url: '/ai/chat/session/list', method: 'get', silent: true })
}

export function getChatSession(sessionId) {
  return request({ url: `/ai/chat/session/${sessionId}`, method: 'get', silent: true })
}

export function delChatSession(sessionId) {
  return request({ url: `/ai/chat/session/${sessionId}`, method: 'delete', silent: true })
}

export function analyzeOneshot(data) {
  return request({ url: '/ai/chat/oneshot', method: 'post', data, timeout: 120000 })
}

export function chatConsultant(data) {
  return request({ url: '/ai/chat/consultant', method: 'post', data, timeout: 120000, silent: true })
}
