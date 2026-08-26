/**
 * 三市场交易时段（按各市场本地时区）。
 * 美股：始终展示（盘前/盘中/盘后/夜盘）；港股、A 股仅开盘时段 isOpen=true。
 */

function zonedClock(timeZone, now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone,
      hour12: false,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit'
    }).formatToParts(now).map((p) => [p.type, p.value])
  )
  const hour = Number(parts.hour === '24' ? 0 : parts.hour)
  const minute = Number(parts.minute)
  const weekend = parts.weekday === 'Sat' || parts.weekday === 'Sun'
  return { minutes: hour * 60 + minute, weekend, hour, minute }
}

function inWindows(minutes, windows) {
  return windows.some(([start, end]) => minutes >= start && minutes < end)
}

/**
 * @param {'US'|'HK'|'CN'} market
 */
export function getMarketSessionStatus(market, now) {
  const m = String(market || '').toUpperCase()
  if (m === 'US') {
    const { minutes, weekend } = zonedClock('America/New_York', now)
    let sessionName = '夜盘'
    let sessionTag = 'overnight'
    let regular = false
    if (!weekend && minutes >= 4 * 60 && minutes < 9 * 60 + 30) {
      sessionName = '盘前'
      sessionTag = 'pre'
    } else if (!weekend && minutes >= 9 * 60 + 30 && minutes < 16 * 60) {
      sessionName = '盘中'
      sessionTag = 'regular'
      regular = true
    } else if (!weekend && minutes >= 16 * 60 && minutes < 20 * 60) {
      sessionName = '盘后'
      sessionTag = 'post'
    } else if (weekend) {
      sessionName = '休市'
      sessionTag = 'closed'
    }
    return {
      isOpen: true,
      regularOpen: regular,
      sessionName,
      sessionTag,
      label: `美股·${sessionName}`
    }
  }

  if (m === 'HK') {
    const { minutes, weekend } = zonedClock('Asia/Hong_Kong', now)
    const isOpen = !weekend && inWindows(minutes, [[9 * 60 + 30, 12 * 60], [13 * 60, 16 * 60]])
    return {
      isOpen,
      regularOpen: isOpen,
      sessionName: isOpen ? '盘中' : (weekend ? '休市' : '已收盘'),
      sessionTag: isOpen ? 'regular' : 'closed',
      label: `港股·${isOpen ? '盘中' : (weekend ? '休市' : '已收盘')}`
    }
  }

  if (m === 'CN') {
    const { minutes, weekend } = zonedClock('Asia/Shanghai', now)
    const isOpen = !weekend && inWindows(minutes, [[9 * 60 + 30, 11 * 60 + 30], [13 * 60, 15 * 60]])
    return {
      isOpen,
      regularOpen: isOpen,
      sessionName: isOpen ? '盘中' : (weekend ? '休市' : '已收盘'),
      sessionTag: isOpen ? 'regular' : 'closed',
      label: `A股·${isOpen ? '盘中' : (weekend ? '休市' : '已收盘')}`
    }
  }

  return { isOpen: false, regularOpen: false, sessionName: '--', sessionTag: 'closed', label: '--' }
}

/** 顶栏：美股始终展示，港股/A 股仅开盘时展示。 */
export function shouldShowMarketChip(market, now) {
  const m = String(market || '').toUpperCase()
  if (m === 'US') return true
  return getMarketSessionStatus(m, now).isOpen
}
