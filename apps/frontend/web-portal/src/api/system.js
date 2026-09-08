import request from '@/utils/request'

export function listUser(query) {
  return request({ url: '/system/user/list', method: 'get', params: query, silent: true })
}

export function listRole(query) {
  return request({ url: '/system/role/list', method: 'get', params: query, silent: true })
}

export function listMenu(query) {
  return request({ url: '/system/menu/list', method: 'get', params: query, silent: true })
}
