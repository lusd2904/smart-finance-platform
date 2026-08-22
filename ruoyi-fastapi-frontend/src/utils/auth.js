import Cookies from 'js-cookie'

const TokenKey = 'Admin-Token'

export function getToken() {
  return Cookies.get(TokenKey)
}

export function setToken(token) {
  // 与后端 JWT_EXPIRE_MINUTES（480 分钟）对齐；不设 expires 会成为会话 Cookie，
  // 浏览器重启后 token 失效行为不一致，且过期后残留风险更高
  return Cookies.set(TokenKey, token, { expires: 0.5 })
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}
