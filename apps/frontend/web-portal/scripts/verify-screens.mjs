import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
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

const shot = async (name) => {
  const file = path.join(outDir, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', file)
}

async function setTheme(id) {
  const label = id === 'glass-light' ? '晨曦白玉 (浅色)' : '幻彩琉璃 (深色)'
  await page.locator('.theme-switcher').first().click()
  await page.getByText(label).click()
  await page.waitForTimeout(500)
}

try {
  await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.glow-title')
  await page.waitForTimeout(700)
  await setTheme('glass-dark')
  await shot('qa1_login_dark.png')
  await setTheme('glass-light')
  await shot('qa1_login_light.png')

  await page.getByRole('button', { name: /演示预览/ }).click()
  await page.waitForURL('**/index')
  await page.waitForSelector('.workbench-page')
  await page.waitForTimeout(800)
  await shot('qa1_workbench_light.png')
  await setTheme('glass-dark')
  await shot('qa1_workbench_dark.png')

  await page.locator('.submenu-item', { hasText: '行情交易' }).first().click()
  await page.waitForURL('**/terminal')
  await page.waitForSelector('.pro-terminal-page')
  await page.waitForTimeout(1000)
  await shot('qa1_terminal_dark.png')
  await setTheme('glass-light')
  await shot('qa1_terminal_light.png')

  const theme = await page.evaluate(() => document.documentElement.dataset.theme)
  console.log(JSON.stringify({ theme, url: page.url(), shots: 6 }))
} catch (err) {
  console.error('VERIFY_FAIL', err.message)
  await shot('qa1_verify_error.png').catch(() => {})
  process.exitCode = 1
} finally {
  await browser.close()
}
