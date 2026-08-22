/**
 * 行情类页面通用格式化工具。
 * 与工作台 dashboard/utils.js 的语义保持一致：红涨绿跌（A股习惯）。
 */
export function fmtPct(val) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '--'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

/** 格式化金额（自动万亿/亿/万单位），可选带货币后缀 */
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

/** 涨跌语义 class：up=红 down=绿 flat=灰 */
export function changeClass(val) {
  const n = Number(val)
  if (!Number.isFinite(n) || n === 0) return 'flat'
  return n > 0 ? 'up' : 'down'
}
