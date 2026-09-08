<template>
  <PageFrame badge="「市场热度 /market/heat」" :loading="loading" hide-hero>
    <section class="heat-hero">
      <div>
        <h2>行情中心</h2>
        <p>
          实时指数 · 收盘热度快照 Top50 · 全市场报价
          <el-tag v-if="heat.asOfTime" size="small" effect="plain" class="asof">快照 {{ snapshotText }}</el-tag>
        </p>
      </div>
      <div class="heat-hero-acts">
        <el-radio-group v-model="market" @change="onMarketChange">
          <el-radio-button value="CN">A股</el-radio-button>
          <el-radio-button value="HK">港股</el-radio-button>
          <el-radio-button value="US">美股</el-radio-button>
        </el-radio-group>
        <el-select v-model="tradeDate" clearable placeholder="交易日" style="width:132px" :loading="datesLoading" @change="loadDaily">
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="refreshAll">刷新</el-button>
      </div>
    </section>

    <div v-if="indices.length" class="index-strip glass-panel">
      <button
        v-for="q in indices"
        :key="q.symbol"
        type="button"
        class="index-item"
        @click="goTerminal($router, q, { tab: 'kline' })"
      >
        <span class="mkt-tag">{{ shortMarket(q.market) }}</span>
        <span>{{ q.name }}</span>
        <strong class="numeric">{{ fmtPx(q.last ?? q.price) }}</strong>
        <em :class="changeClass(q.changePct ?? q.changeRate)">{{ fmtChange(q.changePct ?? q.changeRate) }}</em>
      </button>
    </div>

    <div class="stat-strip">
      <article v-for="card in statCards" :key="card.key" class="stat-tile glass-panel">
        <span>{{ card.label }}</span>
        <strong v-if="card.key === 'breadth'" class="numeric">
          <span class="up">{{ heat.advanceCount ?? '--' }}</span>
          <span> / </span>
          <span class="down">{{ heat.declineCount ?? '--' }}</span>
          <span> / </span>
          <span class="flat">{{ heat.flatCount ?? '--' }}</span>
        </strong>
        <strong v-else :class="card.cls">{{ card.value }}</strong>
        <small>{{ card.sub }}</small>
      </article>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>热度摘要</h3>
              <span class="mkt-tag">{{ marketLabel(market) }} · 收盘</span>
            </div>
          </template>
          <p v-if="heat.heatSummary" class="summary">{{ heat.heatSummary }}</p>
          <el-empty v-else description="暂无热度摘要" :image-size="64" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>近 {{ trendDays }} 日趋势</h3>
              <span class="muted">指数涨跌 / 热度分 / 成交额</span>
            </div>
          </template>
          <div ref="trendRef" class="trend-chart" />
          <el-empty v-if="!trendPoints.length && !loading" description="暂无趋势数据" :image-size="64" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>Top50 热度榜</h3>
          <div class="table-tools">
            <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:180px" />
            <el-radio-group v-model="quickSort" size="small">
              <el-radio-button value="turnover">按成交额</el-radio-button>
              <el-radio-button value="changePct">按涨跌幅</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <el-table :data="sortedTop" stripe max-height="360" empty-text="暂无该市场热度快照，收盘任务完成后将自动写入。">
        <el-table-column prop="rankNo" label="#" width="52" />
        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column label="涨跌%" width="100" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="热度" width="80" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.heatScore ?? row.heat ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column label="成交额亿" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ turnoverYi(row.turnover) }}</span></template>
        </el-table-column>
        <el-table-column label="市场" width="72">
          <template #default="{ row }">{{ shortMarket(row.market || market) }}</template>
        </el-table-column>
        <el-table-column label="档位" width="72">
          <template #default="{ row }">{{ heatTier(row) }}</template>
        </el-table-column>
        <el-table-column width="168">
          <template #default="{ row }">
            <el-button link type="primary" @click="goTerminal($router, row, { tab: 'kline' })">K线</el-button>
            <el-button link type="primary" @click="goTerminal($router, row)">详情</el-button>
            <el-button v-if="!row.inWatchlist" link type="success" :loading="adding === row.symbol" @click="addWatch(row)">加自选</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <button v-if="!showCompare" type="button" class="compare-link" @click="showCompare = true">三列对照（次要）</button>
    <section v-if="showCompare" class="heat-cols">
      <article v-for="card in compareCards" :key="card.market" class="heat-card glass-panel">
        <header class="heat-card-head">
          <span class="mkt-tag">{{ card.market }}</span>
          <strong>{{ card.label }}</strong>
          <span class="muted">{{ card.data.tradeDate || '--' }}</span>
        </header>
        <div class="idx-name">{{ card.data.indexName || '指数' }}</div>
        <b class="idx-chg" :class="changeClass(card.data.indexChangePct)">{{ fmtChange(card.data.indexChangePct) }}</b>
        <div class="muted">热度 {{ card.data.heatScore ?? '--' }} · 涨 {{ card.data.advanceCount ?? '--' }} / 跌 {{ card.data.declineCount ?? '--' }}</div>
      </article>
    </section>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import PageFrame from '@/components/page/PageFrame.vue'
import { getDashboardSummary } from '@/api/dashboard'
import { addMarketWatchlist, getMarketHeatDaily, getMarketHeatDates, getMarketHeatTrend, getMarketIndexQuotes } from '@/api/market'
import { changeClass, fmtAmount, fmtChange, fmtPx } from '@/utils/format'
import { goTerminal, marketLabel, unwrap, unwrapList } from '@/utils/list'
import { stubDashboard } from '@/utils/stubs'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const datesLoading = ref(false)
const market = ref(normalizeMarket(route.query.market) || 'CN')
const tradeDate = ref('')
const dates = ref([])
const heat = ref({})
const meta = ref({})
const top50 = ref([])
const keyword = ref('')
const quickSort = ref('turnover')
const adding = ref('')
const trendPoints = ref([])
const trendDays = 5
const trendRef = ref(null)
const indices = ref([])
const showCompare = ref(false)
const dashHeat = ref({})
let chart

const snapshotText = computed(() => {
  const t = String(heat.value.asOfTime || '')
  return t.length >= 16 ? t.slice(5, 16) : t
})

const statCards = computed(() => {
  const h = heat.value || {}
  const adText = h.advanceCount == null ? '--' : `${h.advanceCount} / ${h.declineCount ?? '--'} / ${h.flatCount ?? '--'}`
  const a = Number(h.advanceCount)
  const d = Number(h.declineCount)
  const adCls = Number.isFinite(a) && Number.isFinite(d) && a !== d ? (a > d ? 'up' : 'down') : ''
  return [
    { key: 'index', label: '指数涨跌%', value: fmtChange(h.indexChangePct), sub: h.indexName || '--', cls: changeClass(h.indexChangePct) },
    { key: 'turnover', label: '样本成交额', value: fmtAmount(h.totalTurnover, meta.value.currency || h.currency), sub: '样本池成交', cls: '' },
    { key: 'breadth', label: '涨 / 跌 / 平', value: adText, sub: '样本池广度', cls: adCls },
    {
      key: 'score',
      label: '热度分',
      value: h.heatScore ?? '--',
      sub: h.asOfTime ? `截至 ${h.asOfTime}` : '待采集',
      cls: Number(h.heatScore) >= 70 ? 'up' : Number(h.heatScore) <= 35 ? 'down' : ''
    }
  ]
})

const sortedTop = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let rows = kw ? top50.value.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw)) : [...top50.value]
  const prop = quickSort.value
  rows.sort((a, b) => (Number(b[prop]) || 0) - (Number(a[prop]) || 0))
  return rows
})

const compareCards = computed(() => {
  const data = dashHeat.value
  const stub = stubDashboard().heat.data
  return ['US', 'HK', 'CN'].map((m) => ({
    market: m,
    label: marketLabel(m),
    data: { ...stub[m], ...(data[m] || {}) }
  }))
})

function normalizeMarket(v) {
  const u = String(v || '').toUpperCase()
  if (u === 'HK' || u === 'US' || u === 'CN') return u
  if (u === 'A') return 'CN'
  return ''
}
function shortMarket(m) {
  if (m === 'US') return '美'
  if (m === 'HK') return '港'
  return 'A'
}
function turnoverYi(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return (n / 1e8).toFixed(1)
}
function heatTier(row) {
  if (row.tier || row.heatTier) return row.tier || row.heatTier
  const s = Number(row.heatScore ?? row.heat)
  if (!Number.isFinite(s)) return '--'
  if (s >= 80) return '高'
  if (s >= 50) return '中'
  return '低'
}

function renderTrend() {
  if (!trendRef.value) return
  if (!chart) chart = echarts.init(trendRef.value)
  const xs = trendPoints.value.map((p) => p.tradeDate)
  const isLight = document.documentElement.dataset.theme === 'glass-light'
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['指数%', '热度', '成交额(亿)'], top: 0, textStyle: { color: isLight ? '#334155' : '#e2e8f0' } },
    grid: { left: 48, right: 24, top: 40, bottom: 28 },
    xAxis: { type: 'category', data: xs, axisLabel: { formatter: (v) => (v ? String(v).slice(5) : v) } },
    yAxis: [
      { type: 'value', name: '指数/热度', scale: true, splitLine: { lineStyle: { opacity: 0.12 } } },
      { type: 'value', name: '成交额', splitLine: { show: false } }
    ],
    series: [
      { name: '指数%', type: 'line', smooth: true, data: trendPoints.value.map((p) => p.indexChangePct), itemStyle: { color: '#f56c6c' } },
      { name: '热度', type: 'line', smooth: true, data: trendPoints.value.map((p) => p.heatScore), itemStyle: { color: '#e6a23c' }, areaStyle: { opacity: 0.08 } },
      { name: '成交额(亿)', type: 'bar', yAxisIndex: 1, data: trendPoints.value.map((p) => Math.round((p.totalTurnover || 0) / 1e8)), itemStyle: { color: '#409eff', opacity: 0.55 } }
    ]
  }, true)
}

async function loadDates() {
  datesLoading.value = true
  try {
    const res = await getMarketHeatDates({ market: market.value, limit: 30 })
    const data = unwrap(res)
    dates.value = (data.dates || unwrapList(res)).map((d) => (typeof d === 'string' ? d : d.tradeDate)).filter(Boolean)
    if (!tradeDate.value && dates.value.length) tradeDate.value = dates.value[dates.value.length - 1]
  } catch {
    dates.value = []
  } finally {
    datesLoading.value = false
  }
}

async function loadTrend() {
  try {
    const res = await getMarketHeatTrend({ market: market.value, days: trendDays })
    trendPoints.value = unwrap(res).points || unwrapList(res)
    await nextTick()
    renderTrend()
  } catch {
    trendPoints.value = []
  }
}

async function loadDaily() {
  loading.value = true
  try {
    const res = await getMarketHeatDaily({ market: market.value, tradeDate: tradeDate.value || undefined })
    const payload = unwrap(res)
    heat.value = payload.heat || payload.snapshot || payload
    meta.value = payload.meta || {}
    top50.value = (payload.top50 || payload.items || []).map((r) => ({ ...r, market: r.market || market.value }))
    if (payload.tradeDate) tradeDate.value = payload.tradeDate
    await loadTrend()
  } catch {
    heat.value = {}
    top50.value = []
  } finally {
    loading.value = false
  }
}

async function loadIndices() {
  try {
    const res = await getMarketIndexQuotes()
    indices.value = unwrapList(res).slice(0, 12)
  } catch {
    indices.value = []
  }
}

async function loadCompare() {
  try {
    const res = await getDashboardSummary()
    dashHeat.value = unwrap(res).heat?.data || {}
  } catch {
    dashHeat.value = stubDashboard().heat.data
  }
}

async function onMarketChange() {
  tradeDate.value = ''
  router.replace({ query: { ...route.query, market: market.value } })
  await loadDates()
  await loadDaily()
}

async function refreshAll() {
  await Promise.all([loadDaily(), loadIndices(), loadCompare()])
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: row.market || market.value, note: 'Top50' })
    row.inWatchlist = true
    ElMessage.success('已加入自选')
  } catch (e) {
    ElMessage.error(e?.message || '加入失败')
  } finally {
    adding.value = ''
  }
}

watch(
  () => route.query.market,
  async (v) => {
    const next = normalizeMarket(v) || 'CN'
    if (next === market.value) return
    market.value = next
    tradeDate.value = ''
    await loadDates()
    await loadDaily()
  }
)

onMounted(async () => {
  if (!route.query.market) router.replace({ query: { ...route.query, market: market.value } })
  await loadDates()
  await refreshAll()
  window.addEventListener('resize', () => chart && chart.resize())
})
onBeforeUnmount(() => {
  chart && chart.dispose()
})
</script>

<style scoped>
.heat-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 24px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%);
  box-shadow: 0 12px 30px rgba(79, 70, 229, 0.22);
}
.heat-hero h2 { margin: 0; font-size: 22px; color: #fff; }
.heat-hero p { margin: 6px 0 0; font-size: 13px; opacity: 0.9; }
.heat-hero-acts { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.asof { margin-left: 8px; vertical-align: middle; }
.index-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
}
.index-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  border: 0;
  border-radius: 9px;
  background: var(--surface-muted);
  color: inherit;
  cursor: pointer;
}
.index-item em { font-style: normal; font-variant-numeric: tabular-nums; }
.card-header, .table-tools { display: flex; align-items: center; gap: 8px; }
.card-header { justify-content: space-between; }
.card-header h3, h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.summary { margin: 0; line-height: 1.7; }
.trend-chart { height: 260px; width: 100%; }
.heat-cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.heat-card { padding: 12px; display: grid; gap: 6px; }
.heat-card-head { display: flex; align-items: center; gap: 8px; }
.heat-card-head .muted { margin-left: auto; }
.idx-chg { font-size: 22px; font-weight: 800; font-variant-numeric: tabular-nums; }
.stat-tile small { color: var(--text-secondary); font-size: 12px; }
.compare-link {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  width: fit-content;
}
@media (max-width: 900px) { .heat-cols { grid-template-columns: 1fr; } }
</style>
