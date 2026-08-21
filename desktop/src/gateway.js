const fs = require('fs')
const path = require('path')

const CONFIG_NAME = 'gateway.json'

const PRESETS = [
  {
    id: 'local-docker',
    label: '本机 Docker',
    url: 'http://127.0.0.1:12580',
    hint: 'docker-compose.sentiment.yml 默认前端网关，已代理 /docker-api',
  },
  {
    id: 'lan',
    label: '局域网',
    url: 'http://192.168.1.10:12580',
    hint: '把 IP 换成这台机器在局域网中的地址',
  },
  {
    id: 'cloud',
    label: '云上 HTTPS',
    url: 'https://your-domain.example',
    hint: '填写已部署的公网前端地址，不是后端 9099/19099 端口',
  },
]

function configPath(userDataDir) {
  return path.join(userDataDir, CONFIG_NAME)
}

function loadGateway(userDataDir) {
  try {
    const raw = fs.readFileSync(configPath(userDataDir), 'utf8')
    const data = JSON.parse(raw)
    if (!data || typeof data !== 'object') return defaultConfig()
    return { ...defaultConfig(), ...data }
  } catch {
    return defaultConfig()
  }
}

function defaultConfig() {
  return {
    url: '',
    confirmOnLaunch: true,
    lastVerifiedAt: null,
  }
}

function saveGateway(userDataDir, payload) {
  const next = {
    ...defaultConfig(),
    ...payload,
    url: normalizeGateway(payload.url),
    updatedAt: new Date().toISOString(),
  }
  fs.mkdirSync(userDataDir, { recursive: true })
  fs.writeFileSync(configPath(userDataDir), JSON.stringify(next, null, 2), 'utf8')
  return next
}

function normalizeGateway(raw) {
  let text = String(raw || '').trim()
  if (!text) return ''
  if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(text)) {
    text = `http://${text}`
  }
  let parsed
  try {
    parsed = new URL(text)
  } catch {
    throw new Error('网关地址格式无效')
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('仅支持 http 或 https 网关')
  }
  return parsed.origin
}

async function probeGateway(rawUrl) {
  let origin
  try {
    origin = normalizeGateway(rawUrl)
  } catch (err) {
    return { ok: false, message: err.message }
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 6000)
  try {
    const pages = await Promise.all(
      ['/', '/login', '/docs'].map(async (pathname) => {
        try {
          const res = await fetch(origin + pathname, {
            method: 'GET',
            redirect: 'follow',
            signal: controller.signal,
            headers: { Accept: 'text/html,application/json;q=0.9,*/*;q=0.8' },
          })
          const contentType = String(res.headers.get('content-type') || '')
          const body = (await res.text()).slice(0, 32000)
          return { pathname, status: res.status, contentType, body }
        } catch (err) {
          return { pathname, error: err.message || String(err) }
        }
      })
    )
    const isFrontend = (page) => {
      const body = page.body || ''
      const type = page.contentType || ''
      if (/swagger-ui|redoc|openapi|FastAPI/i.test(body)) return false
      if (/智慧金融|NEXUS|id="app"/i.test(body)) return true
      return type.includes('text/html') && page.status === 200 && !isApi(page)
    }
    const isApi = (page) => {
      const body = page.body || ''
      const type = page.contentType || ''
      return (
        /swagger-ui|redoc|openapi|FastAPI/i.test(body) ||
        (type.includes('application/json') && /"detail"|"code"/.test(body))
      )
    }
    const htmlPages = pages.filter(isFrontend)
    const apiPages = pages.filter(isApi)
    const appPage = htmlPages.find((page) => page.status && page.status < 500)
    if (appPage) {
      return { ok: true, origin, status: appPage.status, message: '已连通前端网关，可以进入登录' }
    }
    if (apiPages.length && !htmlPages.length) {
      return {
        ok: false,
        origin,
        code: 'api_only',
        message: '这是后端 API 地址。请填写前端网关（本机默认 http://127.0.0.1:12580），不要填 19099/9099。',
      }
    }
    const failed = pages.find((page) => page.status >= 500)
    if (failed) {
      return { ok: false, origin, status: failed.status, message: `网关返回 ${failed.status}，请确认服务已启动` }
    }
    return { ok: false, origin, message: '该地址没有平台前端，请改填 Nginx/前端网关' }
  } catch (err) {
    const aborted = err && err.name === 'AbortError'
    return {
      ok: false,
      origin,
      message: aborted ? '连接超时，请检查地址、端口和防火墙' : `无法连接：${err.message || err}`,
    }
  } finally {
    clearTimeout(timer)
  }
}

module.exports = {
  PRESETS,
  loadGateway,
  saveGateway,
  normalizeGateway,
  probeGateway,
}
