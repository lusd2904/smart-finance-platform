import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const base = process.env.PORTAL_URL || 'http://127.0.0.1:5180'
const outDir = process.env.ARTIFACT_DIR || '/opt/cursor/artifacts'
await mkdir(outDir, { recursive: true })

const browser = await chromium.launch({
  channel: 'chrome',
  args: ['--no-sandbox', '--disable-dev-shm-usage']
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)
await page.route('**/*fonts.googleapis.com/**', (route) => route.abort())
await page.route('**/*fonts.gstatic.com/**', (route) => route.abort())
const cdp = await page.context().newCDPSession(page)

const shot = async (name) => {
  const file = path.join(outDir, name)
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true })
  await writeFile(file, Buffer.from(data, 'base64'))
  console.log('saved', file)
}

async function setTheme(id) {
  await page.evaluate((themeId) => {
    localStorage.setItem('sfp-active-theme', themeId)
    document.documentElement.dataset.theme = themeId
    document.documentElement.style.colorScheme = themeId === 'glass-light' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', themeId !== 'glass-light')
  }, id)
  await page.waitForTimeout(350)
}

async function enterDemo() {
  await page.evaluate(() => {
    sessionStorage.setItem('sfp-demo-session', '1')
    document.cookie = 'Admin-Token=demo-stub-token; path=/'
  })
  await page.goto(`${base}/index`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.workbench-page')
  await page.waitForTimeout(900)
}

try {
  await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.glow-title')
  await page.waitForTimeout(600)
  await setTheme('glass-dark')
  await shot('qa1_shot_login_dark.png')
  await setTheme('glass-light')
  await shot('qa1_shot_login_light.png')

  await enterDemo()
  await shot('qa1_shot_workbench_light.png')
  await setTheme('glass-dark')
  await shot('qa1_shot_workbench_dark.png')

  await page.goto(`${base}/trade/terminal`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.pro-terminal-page')
  await page.waitForTimeout(1000)
  await shot('qa1_shot_terminal_dark.png')
  await setTheme('glass-light')
  await shot('qa1_shot_terminal_light.png')

  const theme = await page.evaluate(() => document.documentElement.dataset.theme).catch(() => 'unknown')
  console.log(JSON.stringify({ theme, url: page.url(), shots: 6 }))
} catch (err) {
  console.error('VERIFY_FAIL', err.message)
  await shot('qa1_shot_verify_error.png').catch(() => {})
  process.exitCode = 1
} finally {
  await browser.close()
}
