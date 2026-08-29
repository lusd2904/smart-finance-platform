import Cookies from 'js-cookie'

const TokenKey = 'Admin-Token'

export function getToken() {
  return Cookies.get(TokenKey)
}

export function setToken(token) {
  // 与后端 JWT_EXPIRE_MINUTES（480 分钟 = 8 小时）对齐
  return Cookies.set(TokenKey, token, {
    expires: 8 / 24,
    sameSite: 'lax',
    secure: typeof location !== 'undefined' && location.protocol === 'https:'
  })
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}
