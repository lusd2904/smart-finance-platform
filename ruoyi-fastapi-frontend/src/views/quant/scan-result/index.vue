<template>
  <div class="app-container scan-result" v-loading="loading">
    <div class="toolbar">
      <el-button icon="ArrowLeft" text @click="$router.back()">返回</el-button>
      <el-select v-model="symbolKey" filterable style="width: 280px" @change="onChange">
        <el-option
          v-for="it in instruments"
          :key="it.symbol + it.market"
          :label="`${it.name || it.symbol} (${it.symbol})`"
          :value="it.symbol + '|' + (it.market || 'US')"
        />
      </el-select>
      <el-button type="primary" plain @click="openDetail">打开标的详情（含AI研判）</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">最新扫描结果</span></template>
          <template v-if="trend">
            <el-space wrap class="mb8">
              <el-tag effect="dark">{{ trend.trendDirection || trend.signal || '--' }}</el-tag>
              <el-tag type="info">评分 {{ trend.technicalScore ?? '--' }}</el-tag>
              <el-tag type="warning">置信度 {{ trend.confidence ?? '--' }}</el-tag>
              <el-tag v-if="trend.riskLevel">{{ riskLabel(trend.riskLevel) }}</el-tag>
            </el-space>
            <div class="headline">{{ trend.headline || '--' }}</div>
            <div class="summary">{{ trend.summary || '--' }}</div>
            <el-descriptions :column="2" border size="small" style="margin-top: 12px">
              <el-descriptions-item label="信号">{{ trend.signal || '--' }}</el-descriptions-item>
              <el-descriptions-item label="时间">{{ trend.createTime || '--' }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="暂无扫描记录，请先在策略页运行策略" :image-size="70" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">最新 AI 研判</span></template>
          <template v-if="ai">
            <el-space wrap class="mb8">
              <el-tag :type="decisionTag(ai.finalDecision)" effect="dark">{{ ai.finalDecision || '--' }}</el-tag>
              <span>置信度 {{ ai.finalConfidence ?? '--' }}%</span>
              <span class="muted">{{ ai.analysisTime || '--' }}</span>
            </el-space>
            <div class="summary">{{ ai.summary || ai.summaryText || '--' }}</div>
            <el-descriptions :column="1" border size="small" style="margin-top: 12px">
              <el-descriptions-item label="趋势">{{ ai.trend || '--' }}</el-descriptions-item>
              <el-descriptions-item label="建议">{{ ai.advice || '--' }}</el-descriptions-item>
            </el-descriptions>
          </template>
          <el-empty v-else description="暂无AI研判，可在标的详情页触发" :image-size="70" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="QuantScanResultIndex">
import { listInstrument } from '@/api/market'
import { getSymbolLatestScan } from '@/api/quant'

const route = useRoute()
const router = useRouter()

const instruments = ref([])
const symbol = ref((route.query.symbol || 'AAPL') + '')
const market = ref((route.query.market || 'US') + '')
const symbolKey = ref(symbol.value + '|' + market.value)
const loading = ref(false)
const trend = ref(null)
const ai = ref(null)

function riskLabel(r) {
  return { low: '低风险', medium: '中风险', high: '高风险' }[String(r).toLowerCase()] || r
}
function decisionTag(d) {
  if (!d) return 'info'
  if (String(d).includes('买') || d === 'BUY') return 'danger'
  if (String(d).includes('卖') || d === 'SELL') return 'success'
  return 'warning'
}
function onChange(val) {
  const [s, m] = String(val).split('|')
  symbol.value = s
  market.value = m || 'US'
  router.replace({ path: '/quant/scan-result', query: { symbol: s, market: m || 'US' } })
  load()
}
function openDetail() {
  router.push({ path: '/market/symbol', query: { symbol: symbol.value, market: market.value } })
}
function load() {
  loading.value = true
  getSymbolLatestScan(symbol.value, { market: market.value })
    .then(res => {
      const data = res.data || {}
      trend.value = data.latestTrendScan || null
      ai.value = data.latestAiAnalysis || null
    })
    .finally(() => {
      loading.value = false
    })
}

onMounted(() => {
  listInstrument().then(res => {
    instruments.value = res.data || []
  })
  load()
})
</script>

<style lang="scss" scoped>
.scan-result {
  .toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 16px;
  }
  .panel {
    border-radius: 12px;
    min-height: 280px;
  }
  .panel-title {
    font-weight: 600;
  }
  .headline {
    font-size: 16px;
    font-weight: 600;
    margin: 8px 0;
  }
  .summary {
    color: #606266;
    line-height: 1.7;
  }
  .muted {
    color: #909399;
    font-size: 12px;
  }
  .mb8 {
    margin-bottom: 8px;
  }
}
</style>
