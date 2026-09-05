<template>
  <div ref="el" class="m-kline"></div>
</template>

<script setup>
import * as echarts from 'echarts'

const props = defineProps({
  bars: { type: Array, default: () => [] },
  period: { type: String, default: 'daily' }
})

const el = ref(null)
let chart

function paint() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  const bars = props.bars || []
  const dates = bars.map((b) => b.date || b.time || '')
  const up = '#E5484D'
  const down = '#30A46C'
  if (props.period === 'intraday') {
    const closes = bars.map((b) => Number(b.close ?? b.last ?? 0))
    chart.setOption({
      animation: false,
      grid: { left: 8, right: 8, top: 12, bottom: 22 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: '#8b8d98' }, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { scale: true, splitLine: { lineStyle: { color: '#f0f1f3' } }, axisLabel: { fontSize: 10, color: '#8b8d98' } },
      series: [{
        type: 'line',
        data: closes,
        showSymbol: false,
        lineStyle: { width: 1.4, color: up },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(229,72,77,0.22)' },
            { offset: 1, color: 'rgba(229,72,77,0.01)' }
          ])
        }
      }]
    }, true)
    return
  }
  const candle = bars.map((b) => [b.open, b.close, b.low, b.high])
  chart.setOption({
    animation: false,
    grid: { left: 8, right: 8, top: 12, bottom: 22 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, color: '#8b8d98' }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { scale: true, splitLine: { lineStyle: { color: '#f0f1f3' } }, axisLabel: { fontSize: 10, color: '#8b8d98' } },
    series: [{
      type: 'candlestick',
      data: candle,
      itemStyle: {
        color: up,
        color0: down,
        borderColor: up,
        borderColor0: down
      }
    }]
  }, true)
}

onMounted(() => {
  paint()
  window.addEventListener('resize', paint)
})
watch(() => [props.bars, props.period], paint, { deep: true })
onBeforeUnmount(() => {
  window.removeEventListener('resize', paint)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.m-kline {
  width: 100%;
  height: 240px;
}
</style>
