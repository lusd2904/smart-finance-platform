/**
 * 可见性自适应轮询：setTimeout 链，busy/idle 间隔可在每次 tick 后切换。
 */

export function pickPollDelay(busy, busyMs = 3000, idleMs = 30000) {
  const busyDelay = Number(busyMs)
  const idleDelay = Number(idleMs)
  const busyMsSafe = Number.isFinite(busyDelay) ? busyDelay : 3000
  const idleMsSafe = Number.isFinite(idleDelay) ? idleDelay : 30000
  return busy ? busyMsSafe : idleMsSafe
}

export function startAdaptivePoll({
  tick,
  isBusy,
  busyMs = 3000,
  idleMs = 30000,
  hiddenStop = true,
} = {}) {
  let timer = null
  let stopped = true
  let visBound = false

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function isHidden() {
    return hiddenStop && typeof document !== 'undefined' && !!document.hidden
  }

  function schedule() {
    clearTimer()
    if (stopped || isHidden()) return
    const busy = typeof isBusy === 'function' ? !!isBusy() : false
    const delay = pickPollDelay(busy, busyMs, idleMs)
    timer = setTimeout(async () => {
      timer = null
      if (stopped || isHidden()) return
      try {
        if (typeof tick === 'function') await tick()
      } catch {
        /* tick 自行处理业务错误 */
      }
      if (!stopped) schedule()
    }, delay)
  }

  function onVisibility() {
    if (!hiddenStop || stopped) return
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      Promise.resolve()
        .then(() => (typeof tick === 'function' ? tick() : undefined))
        .catch(() => {})
        .then(() => {
          if (!stopped) schedule()
        })
    } else {
      clearTimer()
    }
  }

  function bindVis() {
    if (!hiddenStop || visBound || typeof document === 'undefined') return
    document.addEventListener('visibilitychange', onVisibility)
    visBound = true
  }

  function unbindVis() {
    if (!visBound || typeof document === 'undefined') return
    document.removeEventListener('visibilitychange', onVisibility)
    visBound = false
  }

  function start() {
    stopped = false
    bindVis()
    schedule()
  }

  function stop() {
    stopped = true
    clearTimer()
    unbindVis()
  }

  return { start, stop }
}
