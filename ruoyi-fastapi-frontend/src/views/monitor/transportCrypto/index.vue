<template>
  <div class="app-container">
    <!-- 汇总指标卡片 -->
    <SummaryCards :monitor-data="monitorData" />

    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :lg="16">
        <ConfigPanel
          v-model:auto-refresh="autoRefresh"
          :monitor-data="monitorData"
          :loading="loading"
          @refresh="loadMonitorData"
        />
      </el-col>

      <el-col :xs="24" :lg="8">
        <HealthCard :monitor-data="monitorData" />
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :lg="10">
        <FailureReasonChart
          :rows="failureReasonRows"
          :total-count="totalFailureReasonCount"
          :selected-reason="selectedFailureReason"
          @select="selectedFailureReason = $event"
        />
      </el-col>

      <el-col :xs="24" :lg="14">
        <KidStatsChart
          :rows="kidStatRows"
          :current-kid="monitorData.currentKid"
          :selected-kid="selectedKid"
          @select="selectedKid = $event"
        />
      </el-col>
    </el-row>

    <!-- 最近失败记录 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>最近失败记录</span>
          <div class="card-actions compact-actions">
            <span class="card-subtitle">最近 {{ displayedRecentFailures.length }} 条</span>
            <el-tag
              v-if="selectedFailureReason || selectedKid"
              type="info"
              effect="plain"
            >
              已按当前选择联动筛选
            </el-tag>
          </div>
        </div>
      </template>

      <el-table :data="displayedRecentFailures" empty-text="暂无失败记录">
        <el-table-column label="时间" min-width="170">
          <template #default="scope">
            {{ formatMonitorTime(scope.row.time) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="请求方法" prop="method" width="100" align="center">
          <template #default="scope">
            <el-tag effect="plain">{{ scope.row.method || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="请求路径" prop="path" min-width="260" :show-overflow-tooltip="true" />
        <el-table-column label="失败原因" prop="reason" min-width="180">
          <template #default="scope">
            <el-tag :type="getFailureTagType(scope.row.reason)" effect="plain">
              {{ scope.row.reason || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="密钥版本" prop="kid" min-width="140">
          <template #default="scope">
            {{ scope.row.kid || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="TransportCryptoMonitor">
import { getTransportCryptoMonitor } from '@/api/monitor/transportCrypto'
import { createEmptyMonitorData, formatMonitorTime, getFailureTagType } from './utils'
import SummaryCards from './components/SummaryCards.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import HealthCard from './components/HealthCard.vue'
import FailureReasonChart from './components/FailureReasonChart.vue'
import KidStatsChart from './components/KidStatsChart.vue'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const autoRefresh = ref(true)
const selectedFailureReason = ref('')
const selectedKid = ref('')
const monitorData = ref(createEmptyMonitorData())

let refreshTimer = null

const failureReasonRows = computed(() => {
  const failureReasons = monitorData.value.failureReasons || {}
  return Object.keys(failureReasons)
    .map(key => ({
      reason: key,
      count: failureReasons[key]
    }))
    .sort((a, b) => b.count - a.count)
})

const totalFailureReasonCount = computed(() =>
  failureReasonRows.value.reduce((total, item) => total + Number(item.count || 0), 0)
)

const kidStatRows = computed(() =>
  [...(monitorData.value.kidStats || [])].sort((a, b) => {
    const currentKid = monitorData.value.currentKid
    if (a.kid === currentKid && b.kid !== currentKid) {
      return -1
    }
    if (b.kid === currentKid && a.kid !== currentKid) {
      return 1
    }
    const aTotal = Number(a.encryptedRequests || 0) + Number(a.decryptSuccess || 0) + Number(a.decryptFailure || 0)
    const bTotal = Number(b.encryptedRequests || 0) + Number(b.decryptSuccess || 0) + Number(b.decryptFailure || 0)
    return bTotal - aTotal
  })
)

const displayedRecentFailures = computed(() => {
  return (monitorData.value.recentFailures || []).filter(item => {
    const matchesReason = !selectedFailureReason.value || item.reason === selectedFailureReason.value
    const matchesKid = !selectedKid.value || item.kid === selectedKid.value
    return matchesReason && matchesKid
  })
})

function loadMonitorData(showLoading = true) {
  loading.value = true
  if (showLoading) {
    proxy.$modal.loading('正在加载传输加密监控数据，请稍候！')
  }
  getTransportCryptoMonitor().then(response => {
    monitorData.value = {
      ...createEmptyMonitorData(),
      ...response.data
    }
  }).finally(() => {
    loading.value = false
    if (showLoading) {
      proxy.$modal.closeLoading()
    }
  })
}

function resetRefreshTimer() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => {
      loadMonitorData(false)
    }, 15000)
  }
}

watch(autoRefresh, () => {
  resetRefreshTimer()
})

onMounted(() => {
  loadMonitorData()
  resetRefreshTimer()
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style lang="scss" scoped>
@import './components/card-common.scss';

.mb16 {
  margin-bottom: 16px;
}
</style>
