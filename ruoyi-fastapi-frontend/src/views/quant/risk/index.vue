<template>
  <div class="app-container risk-page">
    <div class="page-hero">
      <div>
        <h2>风险概览</h2>
        <p>基于策略扫描信号与自选池，快速查看偏多/偏空与置信度（轻量风控视图）</p>
      </div>
      <div>
        <el-button type="primary" :loading="loading" icon="Refresh" @click="loadData">刷新</el-button>
        <el-button @click="$router.push('/trade/risk')">完整风控</el-button>
        <el-button @click="$router.push('/quant/strategy')">策略中心</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="mb16">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <div class="risk-card" :class="c.tone">
          <div class="label">{{ c.label }}</div>
          <div class="value">{{ c.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" v-loading="loading">
      <template #header>
        <div class="panel-header">
          <span>最近策略信号</span>
          <el-button link type="primary" @click="$router.push('/quant/scan-result')">扫描结果</el-button>
        </div>
      </template>
      <el-table :data="signals" stripe>
        <el-table-column prop="symbol" label="标的" width="120" />
        <el-table-column prop="signal" label="信号" width="100">
          <template #default="{ row }">
            <el-tag :type="signalType(row.signal)" effect="dark">{{ row.signal || '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="100" />
        <el-table-column prop="confidence" label="置信度" width="100" />
        <el-table-column prop="reason" label="理由" min-width="220" show-overflow-tooltip />
        <el-table-column prop="createTime" label="时间" width="170" />
      </el-table>
      <el-empty v-if="!loading && !signals.length" description="暂无信号，请先运行策略扫描" />
    </el-card>
  </div>
</template>

<script setup name="QuantRisk">
import { listStrategyHistory, listWatchlist } from '@/api/quant'

const loading = ref(false)
const signals = ref([])
const watchCount = ref(0)

const cards = computed(() => {
  const bull = signals.value.filter(s => /买|多|BULL|BUY/i.test(String(s.signal || ''))).length
  const bear = signals.value.filter(s => /卖|空|BEAR|SELL/i.test(String(s.signal || ''))).length
  const avgConf = signals.value.length
    ? (signals.value.reduce((a, b) => a + (Number(b.confidence) || 0), 0) / signals.value.length).toFixed(1)
    : '--'
  return [
    { label: '自选标的', value: watchCount.value, tone: 't-blue' },
    { label: '偏多信号', value: bull, tone: 't-red' },
    { label: '偏空信号', value: bear, tone: 't-green' },
    { label: '平均置信度', value: avgConf, tone: 't-purple' }
  ]
})

function signalType(sig) {
  const s = String(sig || '')
  if (/买|多|BUY|BULL/i.test(s)) return 'danger'
  if (/卖|空|SELL|BEAR/i.test(s)) return 'success'
  return 'info'
}

async function loadData() {
  loading.value = true
  try {
    const [hist, wl] = await Promise.all([
      listStrategyHistory({ pageNum: 1, pageSize: 20 }).catch(() => ({ rows: [] })),
      listWatchlist({ pageNum: 1, pageSize: 1 }).catch(() => ({ total: 0 }))
    ])
    signals.value = hist.rows || []
    watchCount.value = wl.total ?? (wl.rows || []).length
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.page-hero {
  display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: #909399; font-size: 13px; }
}
.mb16 { margin-bottom: 16px; }
.risk-card {
  border-radius: 12px; padding: 14px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  .label { font-size: 12px; color: var(--text-muted, #94a3b8); }
  .value { font-size: 24px; font-weight: 700; margin-top: 4px; color: var(--text-emphasis); }
  &.t-blue .value { color: #60a5fa; }
  &.t-red .value { color: var(--stat-up, #dc2626); }
  &.t-green .value { color: var(--stat-down, #059669); }
  &.t-purple .value { color: #a78bfa; }
}
.page-hero h2, .panel-header { color: var(--text-emphasis); }
.page-hero p { color: var(--text-muted); }
.panel-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
</style>
