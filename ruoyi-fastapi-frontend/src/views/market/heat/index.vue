<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>市场热度看板</h2>
        <p>三市场切换 · 收盘快照 Top50 · 与量化自选池同源</p>
      </div>
      <div class="acts">
        <el-radio-group v-model="market" @change="onMarketChange">
          <el-radio-button label="CN">A股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="US">美股</el-radio-button>
        </el-radio-group>
        <el-select v-model="tradeDate" clearable placeholder="交易日" style="width:150px" @change="loadDaily">
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" :loading="loading" icon="Refresh" @click="loadDaily">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="emptyHint" :title="emptyHint" type="info" show-icon class="mb16" :closable="false" />
    <el-alert v-if="staleHint" :title="staleHint" type="warning" show-icon class="mb16" :closable="false" />

    <el-row :gutter="12" class="mb16" v-loading="loading">
      <el-col :xs="24" :sm="6">
        <div class="stat-card">
          <div class="label">指数涨跌</div>
          <div class="value" :class="heat?.indexChangePct >= 0 ? 'up' : 'down'">
            {{ fmtPct(heat?.indexChangePct) }}
          </div>
          <div class="sub">{{ heat?.indexName || '--' }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="stat-card">
          <div class="label">样本成交额</div>
          <div class="value">{{ fmtTurnover(heat?.totalTurnover) }}</div>
          <div class="sub">{{ meta?.currency || '--' }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="stat-card">
          <div class="label">涨 / 跌 / 平</div>
          <div class="value">{{ heat?.advanceCount ?? '--' }} / {{ heat?.declineCount ?? '--' }} / {{ heat?.flatCount ?? '--' }}</div>
          <div class="sub">样本池 A-D</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="stat-card">
          <div class="label">热度分</div>
          <div class="value">{{ heat?.heatScore ?? '--' }}</div>
          <div class="sub">{{ heat?.asOfTime ? `截至 ${heat.asOfTime}` : '待采集' }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="mb16" v-if="heat?.heatSummary">
      <template #header><span>热度摘要</span></template>
      <p class="summary">{{ heat.heatSummary }}</p>
      <p class="rule">Top50 过滤：{{ heat.filterRule || meta?.capFilterRule || '--' }}</p>
    </el-card>

    <el-card shadow="never" class="mb16">
      <template #header><span>近 {{ trendDays }} 日趋势</span></template>
      <div ref="trendRef" class="trend-chart" />
      <el-empty v-if="!trendPoints.length && !loading" description="暂无趋势数据" />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="table-head">
          <span>成交额 Top50</span>
          <span class="muted">排序：</span>
          <el-radio-group v-model="sortBy" size="small">
            <el-radio-button label="turnover">成交额</el-radio-button>
            <el-radio-button label="changePct">涨跌幅</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="sortedTop50" stripe empty-text="暂无 Top50 快照">
        <el-table-column prop="rankNo" label="#" width="50" />
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="marketCap" label="市值" width="130">
          <template #default="{ row }">{{ fmtTurnover(row.marketCap) }}</template>
        </el-table-column>
        <el-table-column prop="turnover" label="成交额" width="130" sortable>
          <template #default="{ row }">{{ fmtTurnover(row.turnover) }}</template>
        </el-table-column>
        <el-table-column prop="changePct" label="涨跌幅%" width="110">
          <template #default="{ row }">
            <span :class="row.changePct >= 0 ? 'up' : 'down'">{{ fmtPct(row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="goSymbol(row)">详情</el-button>
            <el-button
              v-if="!row.inWatchlist"
              link
              type="success"
              :loading="adding === row.symbol"
              @click="addWatch(row)"
            >加自选</el-button>
            <el-tag v-else size="small" type="success">已加入</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="MarketHeat">
import * as echarts from 'echarts'
import { getMarketHeatDaily, getMarketHeatDates, getMarketHeatTrend, addMarketWatchlist } from '@/api/market'

const router = useRouter()
const loading = ref(false)
const market = ref('CN')
const tradeDate = ref('')
const dates = ref([])
const heat = ref(null)
const meta = ref(null)
const top50 = ref([])
const trendPoints = ref([])
const trendDays = 5
const sortBy = ref('turnover')
const adding = ref('')
const trendRef = ref(null)
let chart = null

const emptyHint = computed(() => {
  if (loading.value) return ''
  if (!heat.value && !top50.value.length) return '暂无该市场热度快照，收盘任务完成后将自动写入。'
  return ''
})
const staleHint = computed(() => heat.value?.staleHint || '')

const sortedTop50 = computed(() => {
  const arr = [...top50.value]
  const key = sortBy.value
  arr.sort((a, b) => Number(b[key] || 0) - Number(a[key] || 0))
  return arr
})

function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}
function fmtTurnover(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`
  return n.toFixed(0)
}

function renderTrend() {
  if (!trendRef.value) return
  if (!chart) chart = echarts.init(trendRef.value)
  const xs = trendPoints.value.map(p => p.tradeDate)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['指数%', '热度', '成交额(亿)'] },
    grid: { left: 48, right: 24, top: 40, bottom: 28 },
    xAxis: { type: 'category', data: xs },
    yAxis: [{ type: 'value', name: '指数/热度' }, { type: 'value', name: '成交额' }],
    series: [
      { name: '指数%', type: 'line', data: trendPoints.value.map(p => p.indexChangePct) },
      { name: '热度', type: 'line', data: trendPoints.value.map(p => p.heatScore) },
      { name: '成交额(亿)', type: 'bar', yAxisIndex: 1, data: trendPoints.value.map(p => (p.totalTurnover || 0) / 1e8) }
    ]
  })
}

async function loadDates() {
  const res = await getMarketHeatDates({ market: market.value, limit: 30 })
  dates.value = res.data?.dates || []
  if (!tradeDate.value && dates.value.length) {
    tradeDate.value = dates.value[dates.value.length - 1]
  }
}

async function loadTrend() {
  const res = await getMarketHeatTrend({ market: market.value, days: trendDays })
  trendPoints.value = res.data?.points || []
  nextTick(() => renderTrend())
}

async function loadDaily() {
  loading.value = true
  try {
    const res = await getMarketHeatDaily({
      market: market.value,
      tradeDate: tradeDate.value || undefined
    })
    const payload = res.data || {}
    heat.value = payload.heat
    meta.value = payload.meta
    top50.value = payload.top50 || []
    if (payload.tradeDate) tradeDate.value = payload.tradeDate
    await loadTrend()
  } finally {
    loading.value = false
  }
}

async function onMarketChange() {
  tradeDate.value = ''
  await loadDates()
  await loadDaily()
}

function goSymbol(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: market.value } })
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: market.value, note: 'Top50' })
    row.inWatchlist = true
  } finally {
    adding.value = ''
  }
}

onMounted(async () => {
  await loadDates()
  await loadDaily()
  window.addEventListener('resize', () => chart?.resize())
})
onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})
</script>

<style scoped>
.page-hero { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:10px; }
.acts { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
.page-hero h2 { margin:0 0 4px; color:var(--text-emphasis); }
.page-hero p { margin:0; color:var(--text-muted); font-size:13px; }
.mb16 { margin-bottom:16px; }
.stat-card { background:var(--surface-card,#fff); border:1px solid var(--border-soft); border-radius:14px; padding:14px; margin-bottom:10px; }
.stat-card .label { color:var(--text-muted); font-size:12px; }
.stat-card .value { font-size:22px; font-weight:700; margin:6px 0; }
.stat-card .sub { color:var(--text-muted); font-size:12px; }
.summary { margin:0 0 8px; line-height:1.6; }
.rule { margin:0; color:var(--text-muted); font-size:12px; }
.trend-chart { height:260px; width:100%; }
.table-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.muted { color:var(--text-muted); font-size:12px; }
.up { color:#16a34a; }
.down { color:#dc2626; }
</style>
