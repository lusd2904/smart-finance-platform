/** Mobile H5 path and gray-test force switches. UA routing stays at nginx. */

import Cookies from 'js-cookie'

export const FORCE_MOBILE_COOKIE = 'sfp_m'

export function isMobilePath(path) {
  if (!path) return false
  return path === '/m' || path.startsWith('/m/')
}

/** @returns {1|0|null} */
export function parseMFlag(value) {
  if (value === '1' || value === 1 || value === true || value === 'true') return 1
  if (value === '0' || value === 0 || value === false || value === 'false') return 0
  return null
}

export function isForceMobileQuery(query) {
  return parseMFlag(query && query.m) === 1
}

export function isForcePcQuery(query) {
  return parseMFlag(query && query.m) === 0
}

const COOKIE_OPTS = { expires: 30, sameSite: 'lax', path: '/' }

/**
 * Query wins, then cookie. 1 = force /m, 0 = force PC, null = no override.
 * @returns {1|0|null}
 */
export function readShellForce(query, jar = Cookies) {
  const fromQuery = parseMFlag(query && query.m)
  if (fromQuery != null) return fromQuery
  return parseMFlag(jar.get(FORCE_MOBILE_COOKIE))
}

export function persistShellForce(flag, jar = Cookies) {
  if (flag === 1 || flag === 0) {
    jar.set(FORCE_MOBILE_COOKIE, String(flag), COOKIE_OPTS)
  }
}

/**
 * Where a gray-test force switch should send the current path.
 * @returns {string|null} destination, or null to keep navigating
 */
export function shellForceRedirect(path, force, hasToken) {
  if (force === 0 && isMobilePath(path)) {
    return hasToken ? '/portal' : '/login'
  }
  if (force === 1 && !isMobilePath(path)) {
    return hasToken ? '/m' : '/m/login'
  }
  return null
}

export function isMobileLocation() {
  if (typeof location === 'undefined') return false
  return isMobilePath(location.pathname)
}
