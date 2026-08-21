const urlInput = document.getElementById('url')
const confirmInput = document.getElementById('confirmOnLaunch')
const statusEl = document.getElementById('status')
const probeBtn = document.getElementById('probeBtn')
const enterBtn = document.getElementById('enterBtn')
const form = document.getElementById('form')
const presetsEl = document.getElementById('presets')

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
}

probeBtn.addEventListener('click', async () => {
  setBusy(true)
  setStatus('正在探测网关…')
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
