import Cookies from 'js-cookie'

const TokenKey = 'Admin-Token'

export function getToken() {
  return Cookies.get(TokenKey)
}

/** Real login cookie present (not the demo stub token). */
export function hasLiveSession() {
  const t = getToken()
  return Boolean(t) && t !== 'demo-stub-token'
}

export function setToken(token) {
  return Cookies.set(TokenKey, token, {
    expires: 8 / 24,
    sameSite: 'lax',
    secure: typeof location !== 'undefined' && location.protocol === 'https:'
  })
}

export function removeToken() {
  return Cookies.remove(TokenKey)
}
