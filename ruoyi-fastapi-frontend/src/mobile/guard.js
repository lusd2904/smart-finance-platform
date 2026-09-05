/** Mobile H5 path and self-test helpers. Used by permission + 401 handling. */

export function isMobilePath(path) {
  if (!path) return false
  return path === '/m' || path.startsWith('/m/')
}

export function isForceMobileQuery(query) {
  if (!query) return false
  const v = query.m
  return v === '1' || v === 1 || v === true || v === 'true'
}

export function isMobileLocation() {
  if (typeof location === 'undefined') return false
  return isMobilePath(location.pathname)
}
