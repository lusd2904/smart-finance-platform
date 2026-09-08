/**
 * 舆情大盘「市场情绪分数趋势」ECharts option。
 * 缺失行情/分数保留为 null，靠 connectNulls 把上一有效点连到下一有效点，
 * 不把缺口填成 0，也不做插值。
 */

const SERIES = [
  { key: 'usScore', name: '美股', color: '#409eff' },
  { key: 'hkScore', name: '港股', color: '#e6a23c' },
  { key: 'aScore', name: 'A股', color: '#f56c6c' }
]

/** 缺失或非数字 → null；0 是合法分数，原样保留。 */
export function toTrendScore(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/**
 * @param {Array<{ createTime?: string, usScore?: number|null, hkScore?: number|null, aScore?: number|null }>} list
 * @param {(input: unknown) => string} formatTime
 */
export function buildSentimentTrendOption(list, formatTime) {
  const rows = Array.isArray(list) ? list : []
  const format = typeof formatTime === 'function' ? formatTime : (value) => (value == null ? '' : String(value))
  const times = rows.map((item) => format(item && item.createTime))
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: SERIES.map((s) => s.name), top: 0 },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: times,
      axisLabel: {
        formatter: (value) => (value ? String(value).slice(5, 16) : value)
      }
    },
    yAxis: { type: 'value', name: '分数', min: 0, max: 100 },
    series: SERIES.map((s) => ({
      name: s.name,
      type: 'line',
      smooth: true,
      // 默认 connectNulls=false 会在 null 处断开折线/面积；缺失桶只需跨点相连。
      connectNulls: true,
      data: rows.map((item) => toTrendScore(item && item[s.key])),
      itemStyle: { color: s.color },
      areaStyle: { opacity: 0.08 }
    }))
  }
}
