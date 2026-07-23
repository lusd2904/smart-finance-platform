/**
 * ECharts 深/浅色统一配置
 */
import useSettingsStore from '@/store/modules/settings'

export function isDarkTheme() {
  try {
    return !!useSettingsStore().isDark || document.documentElement.classList.contains('dark')
  } catch (e) {
    return document.documentElement.classList.contains('dark')
  }
}

export function chartTextColor() {
  return isDarkTheme() ? '#cbd5e1' : '#606266'
}

export function chartAxisLine() {
  return isDarkTheme() ? 'rgba(148,163,184,0.35)' : '#dcdfe6'
}

export function chartSplitLine() {
  return isDarkTheme() ? 'rgba(148,163,184,0.12)' : '#ebeef5'
}

export function chartTooltipTheme() {
  if (isDarkTheme()) {
    return {
      backgroundColor: 'rgba(15,23,42,0.92)',
      borderColor: 'rgba(148,163,184,0.25)',
      textStyle: { color: '#e2e8f0' }
    }
  }
  return {
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderColor: '#e4e7ed',
    textStyle: { color: '#303133' }
  }
}

/** 注入到 option 的通用坐标系/提示样式 */
export function applyChartTheme(option = {}) {
  const text = chartTextColor()
  const axis = chartAxisLine()
  const split = chartSplitLine()
  const tip = chartTooltipTheme()
  const next = { ...option }
  next.backgroundColor = 'transparent'
  next.textStyle = { ...(next.textStyle || {}), color: text }
  next.tooltip = { ...(next.tooltip || {}), ...tip, ...(option.tooltip || {}) }
  if (next.legend) {
    next.legend = { ...next.legend, textStyle: { color: text, ...(next.legend.textStyle || {}) } }
  }
  const patchAxis = (ax) => {
    if (!ax) return ax
    const list = Array.isArray(ax) ? ax : [ax]
    return list.map((a) => ({
      ...a,
      axisLabel: { color: text, ...(a.axisLabel || {}) },
      axisLine: { lineStyle: { color: axis }, ...(a.axisLine || {}) },
      splitLine: { lineStyle: { color: split }, ...(a.splitLine || {}) },
      nameTextStyle: { color: text, ...(a.nameTextStyle || {}) }
    }))
  }
  if (next.xAxis) next.xAxis = patchAxis(next.xAxis)
  if (next.yAxis) next.yAxis = patchAxis(next.yAxis)
  return Array.isArray(option.xAxis) || Array.isArray(option.yAxis)
    ? {
        ...next,
        xAxis: Array.isArray(option.xAxis) ? next.xAxis : (next.xAxis && next.xAxis[0]),
        yAxis: Array.isArray(option.yAxis) ? next.yAxis : (next.yAxis && next.yAxis[0])
      }
    : {
        ...next,
        xAxis: next.xAxis && next.xAxis[0],
        yAxis: next.yAxis && next.yAxis[0]
      }
}
