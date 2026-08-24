<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span>密钥版本统计</span>
        <div class="card-actions compact-actions">
          <span class="card-subtitle">观察不同 kid 的运行状态</span>
          <el-tag v-if="selectedKid" type="success" effect="plain" closable @close="$emit('select', '')">
            {{ selectedKid }}
          </el-tag>
        </div>
      </div>
    </template>

    <div v-if="rows.length" ref="chartRef" class="chart-panel" />
    <el-empty v-else description="暂无密钥统计数据" :image-size="88" class="chart-empty" />

    <div class="table-title">明细数据</div>
    <el-table
      :data="displayedRows"
      empty-text="暂无数据"
      max-height="260"
      :row-class-name="getRowClassName"
      @row-click="handleRowClick"
    >
      <el-table-column label="密钥版本" prop="kid" min-width="140">
        <template #default="scope">
          <el-tag :type="scope.row.kid === currentKid ? 'success' : 'info'">
            {{ scope.row.kid || '-' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="加密请求" prop="encryptedRequests" min-width="110" align="center" />
      <el-table-column label="解密成功" prop="decryptSuccess" min-width="110" align="center" />
      <el-table-column label="解密失败" prop="decryptFailure" min-width="110" align="center" />
      <el-table-column label="加密响应" prop="encryptedResponses" min-width="110" align="center" />
      <el-table-column label="成功率" min-width="120" align="center">
        <template #default="scope">
          {{ formatRate(scope.row.decryptSuccess, scope.row.decryptSuccess + scope.row.decryptFailure) }}
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup name="TransportCryptoKidStatsChart">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import echarts from '@/utils/echarts'
import { formatRate } from '../utils'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  currentKid: { type: String, default: '' },
  selectedKid: { type: String, default: '' }
})

const emit = defineEmits(['select'])

const chartRef = ref(null)
let chartInstance = null

const displayedRows = computed(() => {
  if (!props.selectedKid) {
    return props.rows
  }
  return props.rows.filter(item => item.kid === props.selectedKid)
})

function buildBarData(item, value, color) {
  const isSelected = !props.selectedKid || props.selectedKid === item.kid
  return {
    value: Number(value || 0),
    itemStyle: {
      color,
      opacity: isSelected ? 1 : 0.3
    }
  }
}

function bindChartEvents(instance) {
  instance.off('click')
  instance.on('click', params => {
    const targetKid = props.rows[params?.dataIndex]?.kid
    if (!targetKid) {
      return
    }
    emit('select', props.selectedKid === targetKid ? '' : targetKid)
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
    color: ['#409eff', '#67c23a', '#f56c6c', '#909399'],
    legend: {
      top: 0
    },
    grid: {
      top: 48,
      left: 24,
      right: 24,
      bottom: 32,
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        interval: 0,
        rotate: props.rows.length > 4 ? 20 : 0
      },
      data: props.rows.map(item => item.kid || '-')
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: [
      {
        name: '加密请求',
        type: 'bar',
        barMaxWidth: 18,
        data: props.rows.map(item => buildBarData(item, item.encryptedRequests, '#409eff'))
      },
      {
        name: '解密成功',
        type: 'bar',
        barMaxWidth: 18,
        data: props.rows.map(item => buildBarData(item, item.decryptSuccess, '#67c23a'))
      },
      {
        name: '解密失败',
        type: 'bar',
        barMaxWidth: 18,
        data: props.rows.map(item => buildBarData(item, item.decryptFailure, '#f56c6c'))
      },
      {
        name: '加密响应',
        type: 'bar',
        barMaxWidth: 18,
        data: props.rows.map(item => buildBarData(item, item.encryptedResponses, '#909399'))
      }
    ]
  })
}

function handleResize() {
  chartInstance?.resize()
}

function handleRowClick(row) {
  const targetKid = row?.kid || ''
  emit('select', props.selectedKid === targetKid ? '' : targetKid)
}

function getRowClassName({ row }) {
  return props.selectedKid && row.kid === props.selectedKid ? 'selected-table-row' : ''
}

watch(() => props.rows, () => {
  nextTick(renderChart)
})

watch(() => props.selectedKid, () => {
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
