const { app, BrowserWindow, Menu, ipcMain, shell } = require('electron')
const path = require('path')
const { PRESETS, loadGateway, saveGateway, probeGateway, normalizeGateway } = require('./gateway')
const { mustConfigureGateway } = require('./main-boot')

let setupWindow = null
let mainWindow = null

function userDataDir() {
  return app.getPath('userData')
}

function createSetupWindow(notice) {
  if (setupWindow && !setupWindow.isDestroyed()) {
    setupWindow.show()
    setupWindow.focus()
    if (notice) setupWindow.webContents.send('gateway:notice', notice)
    return setupWindow
  }

  setupWindow = new BrowserWindow({
    width: 760,
    height: 680,
    minWidth: 680,
    minHeight: 620,
    title: '智慧金融 · 网关配置',
    backgroundColor: '#070b14',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      // preload.js 仅使用 contextBridge/ipcRenderer（沙箱允许的有限 Node API），可安全开启沙箱
      sandbox: true,
    },
  })
  setupWindow.loadFile(path.join(__dirname, 'setup.html'))
  // 新建窗口分支：等渲染层（含 preload 桥接）就绪后再补发 notice，
  // 否则首启探测失败时新窗口会在监听器挂上之前错过事件。
  if (notice) {
    setupWindow.webContents.once('did-finish-load', () => {
      if (setupWindow && !setupWindow.isDestroyed()) {
        setupWindow.webContents.send('gateway:notice', notice)
      }
    })
  }
  setupWindow.on('closed', () => {
    setupWindow = null
  })
  return setupWindow
}

function createMainWindow(gatewayUrl) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadURL(gatewayUrl)
    mainWindow.show()
    mainWindow.focus()
    return mainWindow
  }

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    title: '智慧金融',
    backgroundColor: '#070b14',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      // 无 preload、仅加载远程网关页面，保持渲染进程沙箱化
      sandbox: true,
    },
  })
  mainWindow.loadURL(gatewayUrl)
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const target = new URL(url)
      const current = new URL(gatewayUrl)
      if (target.origin === current.origin) {
        return { action: 'allow' }
      }
    } catch {
      /* ignore */
    }
    shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.on('closed', () => {
    mainWindow = null
  })
  return mainWindow
}

function buildMenu() {
  const isMac = process.platform === 'darwin'
  const template = [
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: 'about' },
              { type: 'separator' },
              { label: '网关设置…', click: () => createSetupWindow() },
              { type: 'separator' },
              { role: 'hide' },
              { role: 'quit' },
            ],
          },
        ]
      : []),
    {
      label: '平台',
      submenu: [
        { label: '网关设置…', click: () => createSetupWindow() },
        {
          label: '重新加载',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            if (mainWindow && !mainWindow.isDestroyed()) mainWindow.reload()
          },
        },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    { role: 'editMenu' },
    { role: 'viewMenu' },
    { role: 'windowMenu' },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

function registerIpc() {
  ipcMain.handle('gateway:load', () => loadGateway(userDataDir()))
  ipcMain.handle('gateway:presets', () => PRESETS)
  ipcMain.handle('gateway:probe', async (_event, url) => probeGateway(url))
  ipcMain.handle('gateway:enter', async (_event, payload) => {
    const url = normalizeGateway(payload && payload.url)
    const probed = await probeGateway(url)
    if (!probed.ok) {
      return probed
    }
    const saved = saveGateway(userDataDir(), {
      url,
      confirmOnLaunch: true,
      lastVerifiedAt: new Date().toISOString(),
      // last-good：探测通过并成功进入后记录，供下次启动失败时在配置窗展示
      lastGoodUrl: url,
      lastGoodAt: new Date().toISOString(),
    })
    createMainWindow(saved.url)
    if (setupWindow && !setupWindow.isDestroyed()) {
      setupWindow.close()
    }
    return { ok: true, config: saved, probe: probed }
  })
}

async function boot() {
  buildMenu()
  registerIpc()
  if (mustConfigureGateway()) {
    createSetupWindow()
    return
  }
  const config = loadGateway(userDataDir())
  const probed = await probeGateway(config.url)
  if (!probed.ok) {
    // 明确错误态：不自动降级。把失败地址、last-good 与（HTTPS 时）手动降级候选一并交给配置窗，
    // 由用户决定是修正地址还是显式改用 http://。
    createSetupWindow({
      kind: 'probe_failed',
      message: probed.message,
      failedUrl: config.url || '',
      lastGoodUrl: config.lastGoodUrl || null,
      fallbackUrl: probed.fallbackUrl || null,
    })
    return
  }
  createMainWindow(config.url)
}

app.whenReady().then(boot)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    boot()
  }
})
