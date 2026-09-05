/**
 * Client-side gateway probe only — no dedicated backend API.
 * Hits the same captcha image endpoint the login page already uses.
 */
export async function probeGateway(timeoutMs = 4000) {
  const base = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_APP_BASE_API) || ''
  const origin = typeof location !== 'undefined' ? location.origin : ''
  const url = `${origin}${base}/captchaImage`
  const started = Date.now()
  const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
  const timer = setTimeout(() => ctrl?.abort(), timeoutMs)
  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      signal: ctrl?.signal
    })
    clearTimeout(timer)
    return {
      ok: res.ok,
      status: res.status,
      ms: Date.now() - started,
      base: base || '/',
      url
    }
  } catch (err) {
    clearTimeout(timer)
    return {
      ok: false,
      status: 0,
      ms: Date.now() - started,
      base: base || '/',
      url,
      error: err && err.name === 'AbortError' ? 'timeout' : 'unreachable'
    }
  }
}
