<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>AI 研判工作台</h2>
        <p>单标的研判 + 批量扫描任务历史</p>
      </div>
    </div>
    <el-tabs v-model="tab">
      <el-tab-pane label="单标的" name="single">
        <el-form :inline="true" class="mb16">
          <el-form-item label="标的">
            <el-select v-model="symbol" filterable style="width: 160px" @change="onSymbol">
              <el-option v-for="i in instruments" :key="i.symbol" :label="i.symbol + ' ' + i.name" :value="i.symbol" />
            </el-select>
          </el-form-item>
          <el-form-item label="市场">
            <el-select v-model="market" style="width: 100px">
              <el-option label="US" value="US" />
              <el-option label="HK" value="HK" />
              <el-option label="CN" value="CN" />
            </el-select>
          </el-form-item>
          <el-form-item label="天数"><el-input-number v-model="days" :min="30" :max="365" /></el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="runAi">开始研判</el-button>
            <el-button @click="loadLatest">最新结论</el-button>
          </el-form-item>
        </el-form>
        <el-row :gutter="16">
          <el-col :md="10" :xs="24">
            <el-card shadow="never" v-loading="loading">
              <template #header>报价快照</template>
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="标的">{{ symbol }}</el-descriptions-item>
                <el-descriptions-item label="最新价">{{ snap.price ?? '--' }}</el-descriptions-item>
                <el-descriptions-item label="K线条数">{{ snap.klineCount ?? '--' }}</el-descriptions-item>
                <el-descriptions-item label="模型">{{ result.modelName || snap.modelName || '--' }}</el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
          <el-col :md="14" :xs="24">
            <el-card shadow="never" v-loading="loading">
              <template #header>研判结论</template>
              <el-tag v-if="result.finalDecision || result.trend" class="mb8">{{ result.finalDecision || result.trend }}</el-tag>
              <div class="sum">{{ result.summary || result.trendSummary || '暂无结论' }}</div>
              <div class="sub" v-if="result.advice || result.operationAdvice"><b>建议：</b>{{ result.advice || result.operationAdvice }}</div>
              <div class="sub" v-if="result.support"><b>支撑：</b>{{ result.support }} · <b>压力：</b>{{ result.resistance }}</div>
              <div class="sub" v-if="result.riskWarning"><b>风险：</b>{{ result.riskWarning }}</div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
      <el-tab-pane label="批量扫描" name="batch">
        <el-form :inline="true" class="mb16">
          <el-form-item label="市场">
            <el-select v-model="batchMarket" style="width: 100px">
              <el-option label="US" value="US" />
              <el-option label="HK" value="HK" />
              <el-option label="CN" value="CN" />
            </el-select>
          </el-form-item>
          <el-form-item><span class="muted">默认该市场前 8 个非指数标的（耗时较长）</span></el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="batchLoading" @click="runBatch">启动批量研判</el-button>
            <el-button @click="loadBatches">刷新历史</el-button>
          </el-form-item>
        </el-form>
        <el-row :gutter="16">
          <el-col :md="10" :xs="24">
            <el-table :data="batches" size="small" @row-click="showBatch" highlight-current-row>
              <el-table-column prop="batchId" label="批次" width="80" />
              <el-table-column prop="successCount" label="成功" width="70" />
              <el-table-column prop="symbolsCount" label="总数" width="70" />
              <el-table-column prop="summary" label="摘要" min-width="120" />
              <el-table-column prop="createTime" label="时间" width="160" />
            </el-table>
          </el-col>
          <el-col :md="14" :xs="24">
            <el-table :data="batchItems" size="small" v-loading="batchLoading">
              <el-table-column prop="symbol" label="标的" width="100" />
              <el-table-column prop="decision" label="结论" width="100" />
              <el-table-column prop="confidence" label="置信" width="80" />
              <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status === '0' ? 'success' : 'danger'">{{ row.status === '0' ? 'OK' : '失败' }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup name="MarketAiWorkbench">
import { listInstrument, aiAnalyze, getLatestAi, getKline } from '@/api/market'
import { runAiBatch, listAiBatches, listAiBatchItems } from '@/api/trade'

const route = useRoute()
const { proxy } = getCurrentInstance()
const tab = ref('single')
const instruments = ref([])
const symbol = ref(route.query.symbol || 'AAPL')
const market = ref(route.query.market || 'US')
const days = ref(120)
const loading = ref(false)
const result = ref({})
const snap = ref({})
const batchMarket = ref('US')
const batchLoading = ref(false)
const batches = ref([])
const batchItems = ref([])

async function loadInst() {
  const res = await listInstrument()
  instruments.value = res.data || []
}
async function onSymbol() {
  const m = instruments.value.find(i => i.symbol === symbol.value)
  if (m) market.value = m.market || market.value
}
async function loadSnap() {
  const res = await getKline({ symbol: symbol.value, market: market.value, start: '-' + days.value + 'd', stop: 'now()' })
  const kl = (res.data && res.data.klines) || []
  snap.value = { klineCount: kl.length, price: kl.length ? kl[kl.length - 1].close : null }
}
async function runAi() {
  loading.value = true
  try {
    await loadSnap()
    const res = await aiAnalyze({ symbol: symbol.value, market: market.value, days: days.value })
    result.value = res.data || {}
    snap.value = {
      ...snap.value,
      modelName: result.value.modelName,
      price: result.value.price ?? snap.value.price,
      klineCount: result.value.klineCount ?? snap.value.klineCount
    }
    proxy.$modal.msgSuccess(result.value.message || '完成')
  } finally {
    loading.value = false
  }
}
async function loadLatest() {
  loading.value = true
  try {
    const res = await getLatestAi(symbol.value, { market: market.value })
    result.value = res.data || {}
    if (!result.value.summary && result.value.summaryText) result.value.summary = result.value.summaryText
  } finally {
    loading.value = false
  }
}
async function loadBatches() {
  const res = await listAiBatches()
  batches.value = res.data || []
}
async function runBatch() {
  batchLoading.value = true
  try {
    const res = await runAiBatch({ market: batchMarket.value, days: 90 })
    proxy.$modal.msgSuccess(res.msg || '批量完成')
    await loadBatches()
    if (res.data && res.data.batchId) await showBatch({ batchId: res.data.batchId })
  } finally {
    batchLoading.value = false
  }
}
async function showBatch(row) {
  if (!row || !row.batchId) return
  batchLoading.value = true
  try {
    const res = await listAiBatchItems(row.batchId)
    batchItems.value = res.data || []
  } finally {
    batchLoading.value = false
  }
}
onMounted(async () => {
  await loadInst()
  await onSymbol()
  await loadSnap()
  await loadLatest()
  await loadBatches()
})
</script>

<style scoped>
.page-hero { margin-bottom: 12px; }
.page-hero h2 { margin: 0 0 4px; color: var(--text-emphasis); }
.page-hero p { margin: 0; color: var(--text-muted); font-size: 13px; }
.mb16 { margin-bottom: 16px; }
.mb8 { margin-bottom: 8px; }
.sum { line-height: 1.7; color: var(--text-secondary); white-space: pre-wrap; }
.sub { margin-top: 10px; font-size: 13px; color: var(--text-muted); }
.muted { color: var(--text-muted); font-size: 12px; }
</style>
