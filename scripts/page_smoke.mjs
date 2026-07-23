/**
 * 全菜单页面冒烟：登录 → 遍历动态路由 → 检测 404 / 接口失败 / 控制台错误
 * 用法: node scripts/page_smoke.mjs
 */
import { chromium } from 'playwright'
import { execSync } from 'node:child_process'

const BASE = process.env.APP_BASE || 'http://127.0.0.1:12580'
const API = process.env.API_BASE || 'http://127.0.0.1:19099'

function sh(cmd) {
  try { execSync(cmd, { stdio: 'ignore' }) } catch {}
}

// 测试期关验证码（后端使用 Redis DB 2）
sh(`docker exec sentiment-mysql mysql -uroot -proot -e "UPDATE \\\`sentiment-ai\\\`.sys_config SET config_value='false' WHERE config_key='sys.account.captchaEnabled';"`)
sh(`docker exec sentiment-redis redis-cli -n 2 SET sys_config:sys.account.captchaEnabled false`)
sh(`docker exec sentiment-redis redis-cli SET sys_config:sys.account.captchaEnabled false`)

async function loginApi() {
  const body = new URLSearchParams({ username: 'admin', password: 'admin123', code: '', uuid: '' })
  const res = await fetch(`${API}/login`, { method: 'POST', body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  const j = await res.json()
  if (!j.token) throw new Error('login failed: ' + JSON.stringify(j).slice(0, 200))
  return j.token
}

function walkRoutes(nodes, prefix = '', out = []) {
  for (const n of nodes || []) {
    const p = n.path || ''
    let full = p.startsWith('/') ? p : `${prefix}/${p}`.replace(/\/+/g, '/')
    if (!full.startsWith('/')) full = '/' + full
    const comp = n.component
    if (comp && !['Layout', 'ParentView', 'InnerLink'].includes(comp)) {
      out.push({ path: full, title: n.meta?.title || full, component: comp })
    }
    if (n.children?.length) walkRoutes(n.children, full, out)
  }
  return out
}

const results = []
const token = await loginApi()
const routersRes = await fetch(`${API}/getRouters`, { headers: { Authorization: `Bearer ${token}` } })
const routersJson = await routersRes.json()
const routes = walkRoutes(routersJson.data || [])
// 固定页
const fixed = [
  { path: '/portal', title: '门户' },
  { path: '/index', title: '工作台' },
  { path: '/login', title: '登录' },
]
const all = [...fixed, ...routes]

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext()
// 注入 token，模拟已登录
await context.addInitScript((t) => {
  localStorage.setItem('Admin-Token', t)
  // 默认深色，便于抓白块
  document.documentElement.classList.add('dark')
  localStorage.setItem('vueuse-color-scheme', 'dark')
}, token)

const page = await context.newPage()
const apiFails = []
const consoleErrors = []

page.on('response', (res) => {
  const url = res.url()
  if (!url.includes('/docker-api/') && !url.includes(':19099/')) return
  const st = res.status()
  if (st >= 400) {
    apiFails.push({ url: url.replace(/.*\/docker-api/, '').replace(API, ''), status: st })
  }
})
page.on('pageerror', (err) => consoleErrors.push(String(err)))
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})

// 先打开站点写入 token 再跳
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 })
await page.evaluate((t) => {
  localStorage.setItem('Admin-Token', t)
  document.documentElement.classList.add('dark')
}, token)

for (const r of all) {
  if (r.path === '/login') continue
  const item = { path: r.path, title: r.title, ok: true, issues: [] }
  apiFails.length = 0
  consoleErrors.length = 0
  try {
    const resp = await page.goto(`${BASE}${r.path}`, { waitUntil: 'networkidle', timeout: 45000 })
    if (!resp) item.issues.push('no response')
    // 等待一点异步
    await page.waitForTimeout(800)
    const bodyText = await page.locator('body').innerText().catch(() => '')
    if (/404|页面不存在|找不到网页|Not Found/i.test(bodyText) && bodyText.length < 800) {
      item.issues.push('page shows 404 text')
    }
    // 组件 404 标题
    if (await page.locator('text=404').count() && /抱歉|不存在|找不到/.test(bodyText)) {
      item.issues.push('404 component')
    }
    // 接口 4xx/5xx（过滤无关）
    const serious = apiFails.filter(a => a.status >= 500 || a.status === 404 || a.status === 405)
    if (serious.length) item.issues.push('api:' + serious.slice(0, 3).map(a => `${a.status} ${a.url}`).join('; '))
    // 控制台严重错误
    const ce = consoleErrors.filter(t => /Failed to fetch|loadView|Cannot find|is not defined|Unexpected token|404/.test(t))
    if (ce.length) item.issues.push('console:' + ce.slice(0, 2).join(' | ').slice(0, 160))
    // 深色下疑似纯白大块：抽样检测 app-container 背景
    if (r.path !== '/portal') {
      const whiteish = await page.evaluate(() => {
        const nodes = Array.from(document.querySelectorAll('.app-container .el-card, .app-container .stat-card, .app-container .market-card, .app-container .panel-card, .mini-stat, .risk-card'))
        let n = 0
        for (const el of nodes.slice(0, 30)) {
          const bg = getComputedStyle(el).backgroundColor
          const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
          if (!m) continue
          const [r, g, b] = m.slice(1).map(Number)
          if (r > 245 && g > 245 && b > 245) n++
        }
        return n
      })
      if (whiteish >= 3) item.issues.push(`white_blocks=${whiteish}`)
    }
  } catch (e) {
    item.issues.push('nav_error:' + String(e).slice(0, 120))
  }
  item.ok = item.issues.length === 0
  results.push(item)
  console.log(item.ok ? 'PASS' : 'FAIL', r.path, item.issues.join(' | ') || 'ok')
}

await browser.close()

// 恢复验证码
sh(`docker exec sentiment-mysql mysql -uroot -proot -e "UPDATE \\\`sentiment-ai\\\`.sys_config SET config_value='true' WHERE config_key='sys.account.captchaEnabled';"`)
sh(`docker exec sentiment-redis redis-cli SET sys_config:sys.account.captchaEnabled true`)

const failed = results.filter(r => !r.ok)
console.log('\n==== SUMMARY ====')
console.log('total', results.length, 'pass', results.length - failed.length, 'fail', failed.length)
for (const f of failed) console.log(' -', f.path, f.title, '=>', f.issues.join('; '))
process.exit(failed.length ? 1 : 0)
