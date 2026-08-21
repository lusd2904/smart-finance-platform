import { createRequire } from 'node:module'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(fileURLToPath(import.meta.url))
const desktopDir = join(root, '../desktop')
const requireDesktop = createRequire(join(desktopDir, 'package.json'))
const requireFrontend = createRequire(join(root, '../ruoyi-fastapi-frontend/package.json'))
const electronPath = requireDesktop('electron')
const { _electron } = requireFrontend('playwright')

const userData = mkdtempSync(join(tmpdir(), 'sfp-desktop-'))
const app = await _electron.launch({
  executablePath: electronPath,
  args: [desktopDir, `--user-data-dir=${userData}`],
  env: { ...process.env, SFP_FORCE_SETUP: '1' },
})

const setup = await app.firstWindow()
await setup.waitForSelector('#url')
const setupTitle = await setup.title()
await setup.screenshot({ path: join(root, '../output/playwright/desktop-setup.png') })

await setup.fill('#url', 'http://127.0.0.1:19099')
await setup.click('#probeBtn')
await setup.waitForFunction(() => document.querySelector('#status')?.classList.contains('err'))
const apiError = await setup.locator('#status').innerText()

await setup.fill('#url', 'http://127.0.0.1:12580')
await setup.click('#probeBtn')
await setup.waitForFunction(() => document.querySelector('#status')?.classList.contains('ok'))

const windowPromise = app.waitForEvent('window')
await setup.click('#enterBtn')
let main
try {
  main = await windowPromise
} catch {
  main = app.windows().find((win) => win.url().startsWith('http')) || app.windows()[0]
}
await main.waitForLoadState('domcontentloaded')
await main.waitForTimeout(1500)
await main.screenshot({ path: join(root, '../output/playwright/desktop-login.png') })
const body = await main.locator('body').innerText()
const hasLogin = /登录|账号|密码/.test(body)

await main.locator('input[placeholder*="账号"], input[type="text"]').first().fill('admin')
await main.locator('input[placeholder*="密码"], input[type="password"]').first().fill('admin123')
await main.getByRole('button', { name: /登\s*录/ }).click()
await main.waitForTimeout(2500)
await main.screenshot({ path: join(root, '../output/playwright/desktop-after-login.png') })

console.log(JSON.stringify({
  setupTitle,
  apiError,
  loginTitle: await main.title(),
  hasLogin,
  afterUrl: main.url(),
}, null, 2))

await app.close()
