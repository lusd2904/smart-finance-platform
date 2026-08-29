<template>
  <div class="kline-pro">
    <div class="kline-toolbar">
      <el-button-group>
        <el-button size="small" :type="tool === 'segment' ? 'primary' : ''" @click="draw('segment')">趋势线</el-button>
        <el-button size="small" :type="tool === 'horizontalStraightLine' ? 'primary' : ''" @click="draw('horizontalStraightLine')">水平线</el-button>
        <el-button size="small" :type="tool === 'rayLine' ? 'primary' : ''" @click="draw('rayLine')">射线</el-button>
        <el-button size="small" :type="tool === 'rect' ? 'primary' : ''" @click="draw('rect')">矩形</el-button>
        <el-button size="small" :type="tool === 'fibonacciLine' ? 'primary' : ''" @click="draw('fibonacciLine')">斐波那契</el-button>
      </el-button-group>
      <el-button size="small" @click="clearOverlays">清除画线</el-button>
    </div>
    <div v-if="emptyText" class="kline-empty">{{ emptyText }}</div>
    <div ref="hostRef" class="kline-host" v-show="!emptyText" :style="{ height: props.height + 'px' }" />
  </div>
</template>

<script setup>
import { init, dispose } from 'klinecharts'

const props = defineProps({
  klines: { type: Array, default: () => [] },
  liveQuote: { type: Object, default: null },
  height: { type: Number, default: 560 }
})

const hostRef = ref(null)
const tool = ref('')
const emptyText = computed(() => (props.klines && props.klines.length ? '' : '当前标的暂无真实K线'))
let chart = null

function barTime(row) {
  const raw = String(row?.date || '')
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const t = Date.parse(`${raw}T00:00:00+08:00`)
    return Number.isFinite(t) ? t : Date.parse(raw)
  }
  const t = Date.parse(raw.replace(' ', 'T'))
  return Number.isFinite(t) ? t : Date.now()
}

function toBars(rows) {
  return (rows || []).map((row) => ({
    timestamp: barTime(row),
    open: Number(row.open),
    high: Number(row.high),
    low: Number(row.low),
    close: Number(row.close),
    volume: Number(row.volume || 0)
  })).filter((bar) => Number.isFinite(bar.timestamp) && Number.isFinite(bar.close))
}

function dark() {
  return document.documentElement.classList.contains('dark')
}

function styles() {
  const isDark = dark()
  return {
    grid: { show: true, horizontal: { color: isDark ? '#1f2937' : '#eef2f7' }, vertical: { color: isDark ? '#1f2937' : '#eef2f7' } },
    candle: {
      type: 'candle_solid',
      bar: {
        upColor: '#ef5350',
        downColor: '#26a69a',
        noChangeColor: '#888',
        upBorderColor: '#ef5350',
        downBorderColor: '#26a69a',
        upWickColor: '#ef5350',
        downWickColor: '#26a69a'
      }
    },
    xAxis: { axisLine: { color: isDark ? '#334155' : '#dcdfe6' }, tickText: { color: isDark ? '#94a3b8' : '#606266' } },
    yAxis: { axisLine: { color: isDark ? '#334155' : '#dcdfe6' }, tickText: { color: isDark ? '#94a3b8' : '#606266' } },
    crosshair: { horizontal: { text: { backgroundColor: '#6366f1' } }, vertical: { text: { backgroundColor: '#6366f1' } } }
  }
}

function ensureChart() {
  if (chart || !hostRef.value) return chart
  chart = init(hostRef.value, { styles: styles() })
  try { chart.createIndicator('MA', false, { id: 'candle_pane' }) } catch { /* v9 无该 pane id 时忽略 */ }
  try { chart.createIndicator('VOL') } catch { /* ignore */ }
  try { chart.createIndicator('MACD') } catch { /* ignore */ }
  return chart
}

function apply() {
  const inst = ensureChart()
  if (!inst) return
  const bars = toBars(props.klines)
  if (!bars.length) return
  inst.applyNewData(bars, true)
}

function draw(name) {
  if (!chart) return
  tool.value = name
  try {
    chart.createOverlay({ name })
  } catch {
    try { chart.createOverlay(name) } catch { /* ignore */ }
  }
}

function clearOverlays() {
  tool.value = ''
  if (!chart) return
  try { chart.removeOverlay() } catch { /* ignore */ }
}

watch(() => props.klines, () => apply(), { deep: true })
watch(emptyText, (hidden) => { if (!hidden) nextTick(apply) })

watch(() => props.liveQuote, (quote) => {
  if (!chart || !quote) return
  const last = Number(quote.last)
  if (!Number.isFinite(last)) return
  const bars = toBars(props.klines)
  if (!bars.length) return
  const prev = bars[bars.length - 1]
  const next = {
    ...prev,
    close: last,
    high: Math.max(prev.high, last),
    low: Math.min(prev.low, last)
  }
  try { chart.updateData(next) } catch { /* ignore */ }
})

onMounted(() => {
  nextTick(apply)
  window.addEventListener('resize', resize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (chart && hostRef.value) {
    try { dispose(hostRef.value) } catch { /* ignore */ }
  }
  chart = null
})

function resize() {
  try { chart && chart.resize() } catch { /* ignore */ }
}
</script>

<style scoped>
.kline-pro { width: 100%; }
.kline-toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.kline-host { width: 100%; }
.kline-empty { height: 240px; display: flex; align-items: center; justify-content: center; color: var(--text-muted); }
</style>
