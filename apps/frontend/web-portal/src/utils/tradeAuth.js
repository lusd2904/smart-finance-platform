const POS_CACHE = 'sfp-trade-positions-cache'
const ACC_CACHE = 'sfp-trade-account-cache'

export function isBrokerAuthError(err) {
  if (!err) return false
  if (err.brokerAuth) return true
  const code = Number(err.code ?? err?.response?.data?.code)
  if (code === 401004) return true
  const msg = String(err.message || err.msg || '')
  return /401004|access token invalid|longbridge/i.test(msg)
}

export function brokerAuthCode(err) {
  const code = err?.code ?? err?.response?.data?.code
  if (code === 401004 || code === 401) return code
  if (/401004/.test(String(err?.message || ''))) return 401004
  return 401
}

function readJson(key) {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function writeJson(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ ...value, cachedAt: Date.now() }))
  } catch {
    /* ignore quota */
  }
}

export function cacheTradePositions(rows) {
  if (!Array.isArray(rows)) return
  writeJson(POS_CACHE, { rows })
}

export function cacheTradeAccount(account) {
  if (!account || typeof account !== 'object') return
  writeJson(ACC_CACHE, { account })
}

export function readCachedPositions() {
  const data = readJson(POS_CACHE)
  return Array.isArray(data?.rows) ? data.rows : []
}

export function readCachedAccount() {
  return readJson(ACC_CACHE)?.account || null
}
