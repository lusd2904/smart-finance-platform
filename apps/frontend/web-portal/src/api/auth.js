import request from '@/utils/request'

export function login(username, password, code, uuid) {
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)
  if (code) params.append('code', code)
  if (uuid) params.append('uuid', uuid)
  return request({
    url: '/login',
    headers: {
      isToken: false,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    method: 'post',
    data: params
  })
}

export function getInfo() {
  return request({ url: '/getInfo', method: 'get' })
}

export function logout() {
  return request({ url: '/logout', method: 'post' })
}

export function getCodeImg() {
  return request({
    url: '/captchaImage',
    headers: { isToken: false },
    method: 'get',
    timeout: 20000,
    silent: true
  })
}
