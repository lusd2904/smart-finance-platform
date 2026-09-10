import request from '@/utils/request'

export function listUser(query) {
  return request({ url: '/system/user/list', method: 'get', params: query, silent: true })
}

export function getUser(userId) {
  return request({ url: `/system/user/${userId || ''}`, method: 'get', silent: true })
}

export function addUser(data) {
  return request({ url: '/system/user', method: 'post', data })
}

export function updateUser(data) {
  return request({ url: '/system/user', method: 'put', data })
}

export function resetUserPwd(userId, password) {
  return request({ url: '/system/user/resetPwd', method: 'put', data: { userId, password } })
}

export function changeUserStatus(userId, status) {
  return request({ url: '/system/user/changeStatus', method: 'put', data: { userId, status } })
}

export function listRole(query) {
  return request({ url: '/system/role/list', method: 'get', params: query, silent: true })
}

export function getRole(roleId) {
  return request({ url: `/system/role/${roleId}`, method: 'get', silent: true })
}

export function addRole(data) {
  return request({ url: '/system/role', method: 'post', data })
}

export function updateRole(data) {
  return request({ url: '/system/role', method: 'put', data })
}

export function listMenu(query) {
  return request({ url: '/system/menu/list', method: 'get', params: query, silent: true })
}

export function getMenu(menuId) {
  return request({ url: `/system/menu/${menuId}`, method: 'get', silent: true })
}

export function addMenu(data) {
  return request({ url: '/system/menu', method: 'post', data })
}

export function updateMenu(data) {
  return request({ url: '/system/menu', method: 'put', data })
}
