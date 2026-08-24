/**
 * 舆情页统一按北京时间（Asia/Shanghai）展示，不混排 UTC / Z。
 * 朴素 `YYYY-MM-DD HH:mm:ss` / 无 Z 的 ISO 按北京墙上时钟（东财/新浪 pub_time），不当 UTC。
 */
export const BEIJING_TIMEZONE = 'Asia/Shanghai'

function pad(value) {
  return String(value).padStart(2, '0')
}

function partsInBeijing(date) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: BEIJING_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23'
  })
  const bag = {}
  for (const part of fmt.formatToParts(date)) {
    if (part.type !== 'literal') bag[part.type] = part.value
  }
  return bag
}

function parseToDate(input) {
  if (input == null || input === '') return null
  if (input instanceof Date) {
    return Number.isNaN(input.getTime()) ? null : input
  }
  if (typeof input === 'number') {
    const ms = String(input).length === 10 ? input * 1000 : input
    const date = new Date(ms)
    return Number.isNaN(date.getTime()) ? null : date
  }
  const raw = String(input).trim()
  if (!raw) return null

  const hasZone = /[zZ]$/.test(raw) || /[+-]\d{2}:?\d{2}$/.test(raw)
  if (hasZone) {
    const date = new Date(raw)
    return Number.isNaN(date.getTime()) ? null : date
  }

  const matched = raw.match(
    /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?(?:\.\d+)?$/
  )
  if (matched) {
    const [, year, month, day, hour, minute, second] = matched
    // 朴素时间按北京墙上时钟解释：先当成 UTC 再减 8 小时，格式化回上海即原数字
    const date = new Date(Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour) - 8,
      Number(minute),
      Number(second || 0)
    ))
    return Number.isNaN(date.getTime()) ? null : date
  }

  const fallback = new Date(raw)
  return Number.isNaN(fallback.getTime()) ? null : fallback
}

/**
 * 格式化为北京时间 `YYYY-MM-DD HH:mm:ss`（或短格式），不含 Z / UTC 第二行。
 */
export function formatBeijingTime(input, pattern = '{y}-{m}-{d} {h}:{i}:{s}') {
  const date = parseToDate(input)
  if (!date) return ''
  const bag = partsInBeijing(date)
  const map = {
    y: bag.year,
    m: bag.month,
    d: bag.day,
    h: pad(bag.hour === '24' ? '0' : bag.hour),
    i: bag.minute,
    s: bag.second
  }
  return pattern.replace(/{(y|m|d|h|i|s)}/g, (_, key) => map[key] || '00')
}

/** 趋势图短格式：MM-DD HH:mm */
export function formatBeijingTimeShort(input) {
  const full = formatBeijingTime(input, '{y}-{m}-{d} {h}:{i}')
  return full ? full.slice(5) : ''
}
