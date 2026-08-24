import { parseTime } from '@/utils/ruoyi'

export const MODE_LABEL_MAP = {
  required: '强制加密',
  optional: '可选加密',
  off: '已关闭'
}

export const MONITOR_SCOPE_LABEL_MAP = {
  'redis-aggregated': 'Redis 聚合',
  'redis-aggregated+local-fallback': 'Redis 聚合 + 本地回退',
  'process-local-fallback': '本地回退'
}

export function createEmptyMonitorData() {
  return {
    supportedKids: [],
    enabledPaths: [],
    requiredPaths: [],
    excludePaths: [],
    kidStats: [],
    recentFailures: [],
    failureReasons: {}
  }
}

export function formatMonitorTime(value, pattern = '{y}-{m}-{d} {h}:{i}:{s}') {
  if (!value) {
    return null
  }
  if (typeof value === 'string') {
    const normalizedValue = value.trim()
    const microsecondIsoMatch = normalizedValue.match(
      /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/
    )
    if (microsecondIsoMatch) {
      const [, year, month, day, hour, minute, second] = microsecondIsoMatch
      return parseTime(
        new Date(
          Number(year),
          Number(month) - 1,
          Number(day),
          Number(hour),
          Number(minute),
          Number(second)
        ),
        pattern
      )
    }
  }
  return parseTime(value, pattern)
}

export function formatCount(value) {
  return Number(value || 0)
}

export function formatPercent(value, total) {
  if (!total) {
    return '0.0%'
  }
  return `${((Number(value || 0) / total) * 100).toFixed(1)}%`
}

export function formatRate(success, total) {
  return `${getRate(success, total).toFixed(1)}%`
}

export function getRate(numerator, denominator) {
  if (!denominator) {
    return 0
  }
  return (Number(numerator || 0) / Number(denominator || 0)) * 100
}

export function getFailureTagType(reason) {
  const warningReasons = ['timestamp_expired', 'required_missing']
  const dangerReasons = ['decrypt_failed', 'aad_mismatch', 'replay_detected', 'kid_mismatch']

  if (dangerReasons.includes(reason)) {
    return 'danger'
  }
  if (warningReasons.includes(reason)) {
    return 'warning'
  }
  return 'info'
}

export function getFailureChartColor(reason) {
  const tagType = getFailureTagType(reason)
  if (tagType === 'danger') {
    return '#f56c6c'
  }
  if (tagType === 'warning') {
    return '#e6a23c'
  }
  return '#409eff'
}
