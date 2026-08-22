import echarts from '@/utils/echarts'
import { onBeforeUnmount, onMounted, shallowRef } from 'vue'

export function useEChart(elRef) {
  const chart = shallowRef(null)

  function getChart() {
    const el = elRef && elRef.value
    if (!el) return null
    if (!chart.value) chart.value = echarts.init(el)
    return chart.value
  }

  function setOption(option, notMerge = true) {
    const instance = getChart()
    if (instance && option) instance.setOption(option, notMerge)
    return instance
  }

  function resize() {
    if (chart.value) chart.value.resize()
  }

  function dispose() {
    if (chart.value) {
      chart.value.dispose()
      chart.value = null
    }
  }

  onMounted(() => {
    window.addEventListener('resize', resize)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('resize', resize)
    dispose()
  })

  return { chart, getChart, setOption, resize, dispose }
}
