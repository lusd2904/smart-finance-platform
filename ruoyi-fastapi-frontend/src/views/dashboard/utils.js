/**
 * 工作台聚合数据块统一空态/降级判断工具。
 * 后端每个数据块返回 { ok, reason, data }，无权限时 reason='denied'。
 */
export function sectionOk(section) {
  return Boolean(section && section.ok && section.data)
}

export function sectionDenied(section) {
  return Boolean(section && section.reason === 'denied')
}

export function sectionReason(section, fallback = '暂无数据') {
  if (!section) return fallback
  return section.reason || fallback
}

/** 格式化涨跌幅：+x.xx% / -x.xx% / -- */
export function fmtChange(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/** 格式化金额（自动万亿/亿/万单位） */
export function fmtAmount(val, currency) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  const abs = Math.abs(n)
  let text
  if (abs >= 1e12) text = `${(n / 1e12).toFixed(2)} 万亿`
  else if (abs >= 1e8) text = `${(n / 1e8).toFixed(2)} 亿`
  else if (abs >= 1e4) text = `${(n / 1e4).toFixed(2)} 万`
  else text = n.toFixed(2)
  return currency ? `${text} ${currency}` : text
}

/** 涨跌语义色：A股习惯红涨绿跌 */
export function changeClass(val) {
  const n = Number(val)
  if (!Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}
