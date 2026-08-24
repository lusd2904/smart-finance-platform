<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span>失败原因统计</span>
        <div class="card-actions compact-actions">
          <span class="card-subtitle">按 Redis 聚合口径统计</span>
          <el-tag v-if="selectedReason" type="danger" effect="plain" closable @close="$emit('select', '')">
            {{ selectedReason }}
          </el-tag>
        </div>
      </div>
    </template>

    <div v-if="rows.length" ref="chartRef" class="chart-panel" />
    <el-empty v-else description="暂无失败记录" :image-size="88" class="chart-empty" />

    <div class="table-title">明细数据</div>
    <el-table
      :data="displayedRows"
      empty-text="暂无失败记录"
      max-height="260"
      :row-class-name="getRowClassName"
      @row-click="handleRowClick"
    >
      <el-table-column label="失败原因" prop="reason" min-width="180">
        <template #default="scope">
          <el-tag :type="getFailureTagType(scope.row.reason)" effect="plain">
            {{ scope.row.reason }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="次数" prop="count" width="100" align="center" />
      <el-table-column label="占比" width="120" align="center">
        <template #default="scope">
          {{ formatPercent(scope.row.count, totalCount) }}
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup name="TransportCryptoFailureReasonChart">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import echarts from '@/utils/echarts'
import { formatPercent, getFailureChartColor, getFailureTagType } from '../utils'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  totalCount: { type: Number, default: 0 },
  selectedReason: { type: String, default: '' }
})

const emit = defineEmits(['select'])

const chartRef = ref(null)
let chartInstance = null

const displayedRows = computed(() => {
  if (!props.selectedReason) {
    return props.rows
  }
  return props.rows.filter(item => item.reason === props.selectedReason)
})

function bindChartEvents(instance) {
  instance.off('click')
  instance.on('click', params => {
    const targetReason = props.rows[params?.dataIndex]?.reason
    if (!targetReason) {
      return
    }
    emit('select', props.selectedReason === targetReason ? '' : targetReason)
  })
}

function initChart() {
  if (!chartRef.value) {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    return null
  }
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
    bindChartEvents(chartInstance)
  }
  return chartInstance
}

function renderChart() {
  if (!props.rows.length) {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
    return
  }
  const instance = initChart()
  if (!instance) {
    return
  }

  instance.setOption({
    animationDuration: 400,
    color: props.rows.map(item => getFailureChartColor(item.reason)),
    grid: {
      top: 16,
      left: 120,
      right: 24,
      bottom: 16,
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter(params) {
        const currentItem = params?.[0]
        if (!currentItem) {
          return ''
        }
        const currentRow = props.rows[currentItem.dataIndex]
        return `${currentRow.reason}<br/>次数：${currentRow.count}<br/>占比：${formatPercent(currentRow.count, props.totalCount)}`
      }
    },
    xAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    yAxis: {
      type: 'category',
      data: props.rows.map(item => item.reason),
      axisTick: {
        show: false
      }
    },
    series: [
      {
        name: '失败次数',
        type: 'bar',
        barMaxWidth: 22,
        data: props.rows.map(item => ({
          value: Number(item.count || 0),
          itemStyle: {
            color: getFailureChartColor(item.reason),
            opacity: !props.selectedReason || props.selectedReason === item.reason ? 1 : 0.35,
            borderRadius: [0, 6, 6, 0]
          }
        })),
        label: {
          show: true,
          position: 'right'
        }
      }
    ]
  })
}

function handleResize() {
  chartInstance?.resize()
}

function handleRowClick(row) {
  const targetReason = row?.reason || ''
  emit('select', props.selectedReason === targetReason ? '' : targetReason)
}

function getRowClassName({ row }) {
  return props.selectedReason && row.reason === props.selectedReason ? 'selected-table-row' : ''
}

watch(() => props.rows, () => {
  nextTick(renderChart)
})

watch(() => props.selectedReason, () => {
  nextTick(renderChart)
})

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style lang="scss" scoped>
@import './card-common.scss';
@import './chart-panel.scss';
</style>
