/**
 * 上线前 Web 关键路径：登录 → 工作台 / 自选清单 / 因子 / 交易台
 * 用法: APP_BASE=http://127.0.0.1:12580 API_BASE=http://127.0.0.1:19099 npm run e2e:web
 */
import { chromium } from 'playwright'

const BASE = process.env.APP_BASE || 'http://127.0.0.1:12580'
const API = process.env.API_BASE || 'http://127.0.0.1:19099'

async function loginApi() {
  const body = new URLSearchParams({ username: 'admin', password: 'admin123', code: '', uuid: '' })
  const res = await fetch(`${API}/login`, { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  const json = await res.json()
  if (!json.token) throw new Error('login failed: ' + JSON.stringify(json).slice(0, 240))
  return json.token
}

const token = await loginApi()
const pages = [
  { path: '/index', text: '快捷导航' },
  { path: '/market/watchlist', text: '自选清单' },
  { path: '/quant/factor', text: '因子' },
  { path: '/quant/strategy-config', text: '策略配置' },
  { path: '/trade/trading', text: '交易台' },
  { path: '/trade/orders', text: '订单' },
]

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext()
await context.addCookies([
  { name: 'Admin-Token', value: token, url: BASE },
])
await context.addInitScript((t) => {
  localStorage.setItem('Admin-Token', t)
  document.cookie = 'Admin-Token=' + t + '; path=/'
}, token)
const page = await context.newPage()
const failures = []

for (const item of pages) {
  const apiFails = []
  const onResp = (res) => {
    const url = res.url()
    if (!url.includes('/docker-api/') && !url.includes(':19099/')) return
    if (res.status() >= 500) apiFails.push(`${res.status()} ${url}`)
  }
  page.on('response', onResp)
  try {
    await page.goto(BASE + item.path, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForTimeout(2500)
    const body = await page.locator('body').innerText()
    if (!body.includes(item.text)) {
      failures.push(`${item.path} missing text "${item.text}"`)
    }
    if (apiFails.length) {
      failures.push(`${item.path} api: ${apiFails.slice(0, 3).join('; ')}`)
    } else if (body.includes(item.text)) {
      console.log('ok', item.path)
    }
  } catch (err) {
    failures.push(`${item.path} ${err.message || err}`)
  } finally {
    page.off('response', onResp)
  }
}

await browser.close()
if (failures.length) {
  console.error(failures.join('\n'))
  process.exit(1)
}
console.log('web e2e passed', pages.length, 'pages')
