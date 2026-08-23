const urlInput = document.getElementById('url')
const confirmInput = document.getElementById('confirmOnLaunch')
const statusEl = document.getElementById('status')
const probeBtn = document.getElementById('probeBtn')
const enterBtn = document.getElementById('enterBtn')
const form = document.getElementById('form')
const presetsEl = document.getElementById('presets')
const noticeEl = document.getElementById('notice')
const noticeTitleEl = document.getElementById('noticeTitle')
const noticeDetailEl = document.getElementById('noticeDetail')
const fallbackBtn = document.getElementById('fallbackBtn')

function setStatus(text, kind) {
  statusEl.textContent = text || ''
  statusEl.className = 'status' + (kind ? ` ${kind}` : '')
}

function setBusy(busy) {
  probeBtn.disabled = busy
  enterBtn.disabled = busy
}

function renderPresets(items) {
  presetsEl.innerHTML = ''
  for (const item of items) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'preset'
    btn.dataset.id = item.id
    btn.innerHTML = `<b>${item.label}</b><span>${item.hint}</span>`
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset').forEach((el) => el.classList.remove('active'))
      btn.classList.add('active')
      urlInput.value = item.url
      urlInput.focus()
      setStatus('')
    })
    presetsEl.appendChild(btn)
  }
}

async function boot() {
  const [config, presets] = await Promise.all([window.desktop.loadConfig(), window.desktop.presets()])
  renderPresets(presets)
  urlInput.value = config.url || 'http://127.0.0.1:12580'
  confirmInput.checked = config.confirmOnLaunch !== false
  if (config.url) {
    const match = presets.find((item) => item.url === config.url)
    if (match) {
      const node = document.querySelector(`[data-id="${match.id}"]`)
      if (node) node.classList.add('active')
    }
  } else {
    const local = document.querySelector('[data-id="local-docker"]')
    if (local) local.classList.add('active')
  }
  listenGatewayNotice()
}

let currentFallbackUrl = ''

function hideNotice() {
  noticeEl.hidden = true
  noticeTitleEl.textContent = ''
  noticeDetailEl.textContent = ''
  fallbackBtn.hidden = true
  currentFallbackUrl = ''
}

function showNotice(notice) {
  const kindText = notice.kind === 'probe_failed' ? '网关探测失败' : '配置异常'
  const lines = []
  if (notice.failedUrl) lines.push(`失败地址：${notice.failedUrl}`)
  if (notice.lastGoodUrl) {
    lines.push(`上次可用地址：${notice.lastGoodUrl}`)
  } else {
    lines.push('尚无最近一次探测通过的地址记录')
  }
  noticeTitleEl.textContent = `${kindText}：${notice.message || '无法连接网关，请检查地址或网络'}`
  noticeDetailEl.textContent = lines.join('；')
  if (notice.fallbackUrl) {
    currentFallbackUrl = notice.fallbackUrl
    fallbackBtn.hidden = false
    fallbackBtn.textContent = `使用备用地址 ${notice.fallbackUrl}`
  } else {
    currentFallbackUrl = ''
    fallbackBtn.hidden = true
  }
  setStatus('请修正网关地址后再试。', 'err')
  urlInput.focus()
}

fallbackBtn.addEventListener('click', () => {
  if (!currentFallbackUrl) return
  // 仅填充输入框：不自动保存、不自动进入，用户仍需手动确认（显式降级语义）
  urlInput.value = currentFallbackUrl
  document.querySelectorAll('.preset').forEach((el) => el.classList.remove('active'))
  hideNotice()
  urlInput.focus()
  setStatus('已填入备用 HTTP 地址，请点击「测试连接」确认后再「保存并进入登录」。', '')
})

// 监听主进程推送的 gateway:notice（依赖 preload 暴露 onGatewayNotice 桥接；
// 若桥接缺失则静默跳过，不影响既有手动探测流程）
function listenGatewayNotice() {
  const desktop = window.desktop
  if (!desktop || typeof desktop.onGatewayNotice !== 'function') return
  desktop.onGatewayNotice((notice) => {
    if (!notice || !notice.kind) return
    showNotice(notice)
  })
}

probeBtn.addEventListener('click', async () => {
  setBusy(true)
  setStatus('正在探测网关…')
  hideNotice()
  try {
    const result = await window.desktop.probe(urlInput.value)
    setStatus(result.message, result.ok ? 'ok' : 'err')
  } catch (err) {
    setStatus(err.message || String(err), 'err')
  } finally {
    setBusy(false)
  }
})
form.addEventListener('submit', async (event) => {
  event.preventDefault()
  setBusy(true)
  setStatus('正在保存并打开登录页…')
  try {
    const result = await window.desktop.enter({
      url: urlInput.value,
      confirmOnLaunch: confirmInput.checked,
    })
    if (!result.ok) {
      setStatus(result.message || '无法进入平台', 'err')
      setBusy(false)
    }
  } catch (err) {
    setStatus(err.message || String(err), 'err')
    setBusy(false)
  }
})

boot()
