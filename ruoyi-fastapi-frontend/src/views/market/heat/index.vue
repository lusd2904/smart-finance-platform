<template>
  <div class="app-container market-center">
    <!-- 渐变 Hero：标题 + 三市场切换 + 交易日 + 刷新 -->
    <div class="hero-card mb16">
      <div class="hero-left">
        <div class="hero-title">行情中心</div>
        <div class="hero-sub">
          实时指数 · 收盘热度快照 Top50 · 全市场报价
          <el-tag v-if="heat && heat.asOfTime" size="small" effect="plain" class="asof-tag">
            快照 {{ heat.asOfTime.slice(5, 16) }}
          </el-tag>
        </div>
      </div>
      <div class="hero-actions">
        <el-radio-group v-model="market" class="market-switch" @change="onMarketChange">
          <el-radio-button label="CN">A股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="US">美股</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="tradeDate"
          clearable
          placeholder="交易日"
          style="width: 132px"
          :loading="datesLoading"
          @change="loadDaily"
        >
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" icon="Refresh" :loading="loading" @click="refreshAll(true)">刷新</el-button>
      </div>
    </div>

    <!-- 盘中实时指数条：谁在盘中显示谁，不开盘整体隐藏 -->
    <market-index-strip ref="indexStripRef" class="mb16" />

    <!-- 热度四卡：指数涨跌 / 样本成交额 / 涨跌家数 / 热度分 -->
    <el-row :gutter="12" class="mb16" v-loading="loading">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.key">
        <div class="stat-card" @click="card.go && card.go()">
          <div class="stat-icon" :class="`icon-${card.key}`">
            <el-icon><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value" :class="card.cls">{{ card.value }}</div>
            <div class="stat-sub">{{ card.sub }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-alert
      v-if="emptyHint"
      :title="emptyHint"
      type="info"
      show-icon
      class="mb16"
      :closable="false"
    />
    <el-alert v-if="staleHint" :title="staleHint" type="warning" show-icon class="mb16" :closable="false" />

    <!-- 摘要 + 趋势 双栏 -->
    <el-row :gutter="12" class="mb16">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="panel-card block-gap">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">热度摘要</span>
              <span class="panel-sub">{{ heat?.filterRule || meta?.capFilterRule || '' }}</span>
            </div>
          </template>
          <p class="summary" v-if="heat?.heatSummary">{{ heat.heatSummary }}</p>
          <el-empty v-else description="暂无热度摘要" :image-size="70" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="panel-card block-gap">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">近 {{ trendDays }} 日趋势</span>
              <span class="panel-sub">指数涨跌 / 热度分 / 成交额</span>
            </div>
          </template>
          <div ref="trendRef" class="trend-chart" />
          <el-empty v-if="!trendPoints.length && !loading" description="暂无趋势数据" :image-size="70" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Top50 表格 -->
    <el-card shadow="never" class="mb16">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">成交额 Top50</span>
          <div class="table-tools">
            <el-input
              v-model="keyword"
              clearable
              placeholder="代码/名称过滤"
              prefix-icon="Search"
              style="width: 180px"
              size="small"
            />
            <el-radio-group v-model="quickSort" size="small">
              <el-radio-button label="turnover">按成交额</el-radio-button>
              <el-radio-button label="changePct">按涨跌幅</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      <el-table
        :data="sortedTop50"
        stripe
        empty-text="暂无 Top50 快照"
        @sort-change="onTableSort"
        :default-sort="{ prop: 'turnover', order: 'descending' }"
      >
        <el-table-column prop="rankNo" label="#" width="52" />
        <el-table-column prop="symbol" label="代码" width="112" sortable="custom">
          <template #default="{ row }"><span class="mono">{{ row.symbol }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="marketCap" label="市值" width="118" align="right" sortable="custom">
          <template #default="{ row }">{{ fmtAmount(row.marketCap) }}</template>
        </el-table-column>
        <el-table-column prop="turnover" label="成交额" width="122" align="right" sortable="custom">
          <template #default="{ row }">
            <span class="mono">{{ fmtAmount(row.turnover) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="changePct" label="涨跌幅" width="104" align="right" sortable="custom">
          <template #default="{ row }">
            <span class="chg-cell" :class="changeClass(row.changePct)">{{ fmtPct(row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="172" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="goSymbol(row)">详情</el-button>
            <el-button link type="primary" @click="goKline(row)">K线</el-button>
            <el-button
              v-if="!row.inWatchlist"
              link
              type="success"
              :loading="adding === row.symbol"
              @click="addWatch(row)"
            >加自选</el-button>
            <el-tag v-else size="small" type="success" effect="plain">已加入</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 全市场报价板：WS 最新价，60s REST 刷新名称/结构 -->
    <el-card shadow="never" v-loading="boardLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">全市场报价</span>
          <div class="table-tools">
            <el-radio-group v-model="boardMarket" size="small" @change="loadBoard(false)">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="US">美股</el-radio-button>
              <el-radio-button label="HK">港股</el-radio-button>
              <el-radio-button label="CN">A股</el-radio-button>
            </el-radio-group>
            <span class="live-dot-wrap">
              <span class="live-dot"></span>
              <span class="panel-sub">实时最新价{{ boardStale ? ' · 缓存' : '' }}</span>
            </span>
          </div>
        </div>
      </template>
      <el-table
        :data="sortedBoard"
        stripe
        size="default"
        empty-text="报价缓存尚未生成，请等待任务预热"
        max-height="480"
        @sort-change="onBoardSort"
      >
        <el-table-column prop="market" label="市场" width="76" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ marketLabel(row.market) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="116" sortable="custom">
          <template #default="{ row }"><span class="mono">{{ row.symbol }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="price" label="最新价" width="108" align="right" sortable="custom">
          <template #default="{ row }"><span class="mono">{{ row.price ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column prop="changeRate" label="涨跌幅" width="106" align="right" sortable="custom">
          <template #default="{ row }">
            <span class="chg-cell" :class="row.up ? 'up' : 'down'">{{ row.changeText }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="goKline(row)">K线</el-button>
            <el-button link type="primary" @click="goSymbol(row)">详情</el-button>
            <el-button link type="primary" @click="goAi(row)">AI研判</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="MarketHeat">
import { applyChartTheme } from '@/utils/echartsTheme'
import { useEChart } from '@/composables/useEChart'
import { changeClass, fmtAmount, fmtPct } from '@/utils/format'
import {
  getMarketHeatDaily,
  getMarketHeatDates,
  getMarketHeatTrend,
  getBoardQuotes,
  addMarketWatchlist
} from '@/api/market'
import { applyQuotePatch, getQuotesHub } from '@/composables/useMarketQuotesWs'

const route = useRoute()
const router = useRouter()

// ---- 市场与交易日（支持 ?market=US/HK/CN 深链，来自工作台三市场卡片）----
const market = ref('CN')
const tradeDate = ref('')
const dates = ref([])
const datesLoading = ref(false)
const loading = ref(false)
const heat = ref(null)
const meta = ref(null)
const top50 = ref([])
const trendPoints = ref([])
const trendDays = 5

// ---- Top50 过滤/排序：radio 定主序，表头可微调同字段方向；keyword 前端过滤 ----
const keyword = ref('')
const quickSort = ref('turnover')
const tableSort = ref({ prop: '', order: '' })
const boardSort = ref({ prop: '', order: '' })
const adding = ref('')

// ---- 全市场报价板 ----
const boardLoading = ref(false)
const boardMarket = ref('')
const boardRows = ref([])
let quoteTimer = null
let unsubQuotes = null

// ---- 趋势图 ----
const trendRef = ref(null)
const { setOption: setTrendOption, dispose: disposeTrend } = useEChart(trendRef)

// ---- 实时指数条 ----
const indexStripRef = ref(null)

const MARKET_LABELS = { US: '美股', HK: '港股', CN: 'A股', us: '美股', hk: '港股', a: 'A股', cn: 'A股' }
function marketLabel(market) {
  return MARKET_LABELS[String(market || '')] || market || ''
}

const emptyHint = computed(() => {
  if (loading.value) return ''
  if (!heat.value && !top50.value.length) return '暂无该市场热度快照，收盘任务完成后将自动写入。'
  return ''
})
const staleHint = computed(() => heat.value?.staleHint || '')

/** 四张统计卡的统一数据源 */
const statCards = computed(() => {
  const h = heat.value || {}
  const idxCls = Number.isFinite(Number(h.indexChangePct)) ? changeClass(h.indexChangePct) : ''
  const adText =
    h.advanceCount == null ? '--' : `${h.advanceCount} / ${h.declineCount ?? '--'} / ${h.flatCount ?? '--'}`
  const adCls = (() => {
    const a = Number(h.advanceCount)
    const d = Number(h.declineCount)
    if (!Number.isFinite(a) || !Number.isFinite(d) || a === d) return ''
    return a > d ? 'up' : 'down'
  })()
  return [
    {
      key: 'index',
      label: '指数涨跌',
      value: fmtPct(h.indexChangePct),
      sub: h.indexName || '--',
      cls: idxCls,
      icon: 'TrendCharts',
      go: null
    },
    {
      key: 'turnover',
      label: '样本成交额',
      value: fmtAmount(h.totalTurnover),
      sub: meta.value?.currency || '',
      cls: '',
      icon: 'Coin',
      go: null
    },
    {
      key: 'breadth',
      label: '涨 / 跌 / 平',
      value: adText,
      sub: '样本池广度',
      cls: adCls,
      icon: 'Grid',
      go: null
    },
    {
      key: 'score',
      label: '热度分',
      value: h.heatScore ?? '--',
      sub: h.asOfTime ? `截至 ${h.asOfTime}` : '待采集',
      cls: Number(h.heatScore) >= 70 ? 'up' : Number(h.heatScore) <= 35 ? 'down' : '',
      icon: 'Histogram',
      go: null
    }
  ]
})

/** 排序优先级：表头点击 > radio 快捷；关键字始终前端过滤 */
const filteredTop50 = computed(() => {
  const kw = String(keyword.value || '').trim().toUpperCase()
  if (!kw) return top50.value
  return top50.value.filter(
    r => String(r.symbol || '').toUpperCase().includes(kw) || String(r.name || '').toUpperCase().includes(kw)
  )
})
const sortedTop50 = computed(() => sortRows(filteredTop50.value, effectiveSort('top')))
const sortedBoard = computed(() => sortRows(boardRows.value, effectiveSort('board')))

function effectiveSort(kind) {
  if (kind === 'top') {
    if (tableSort.value.prop) return tableSort.value
    return { prop: quickSort.value, order: 'descending' }
  }
  if (boardSort.value.prop) return boardSort.value
  return { prop: 'changeRate', order: 'descending' }
}

function sortRows(rows, { prop, order }) {
  if (!prop || !order) return rows
  const dir = order === 'ascending' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = a[prop] == null ? -Infinity : Number(a[prop])
    const bv = b[prop] == null ? -Infinity : Number(b[prop])
    const an = Number.isFinite(av) ? av : -Infinity
    const bn = Number.isFinite(bv) ? bv : -Infinity
    return (an - bn) * dir || String(a.symbol).localeCompare(String(b.symbol))
  })
}

function onTableSort({ prop, order }) {
  tableSort.value = order ? { prop, order } : { prop: '', order: '' }
}

function onBoardSort({ prop, order }) {
  boardSort.value = order ? { prop, order } : { prop: '', order: '' }
}

// ---- 数据加载 ----
async function loadDates() {
  datesLoading.value = true
  try {
    const res = await getMarketHeatDates({ market: market.value, limit: 30 })
    dates.value = res.data?.dates || []
    // 无深链日期时默认选最近一日
    if (!tradeDate.value && dates.value.length) tradeDate.value = dates.value[dates.value.length - 1]
  } finally {
    datesLoading.value = false
  }
}

async function loadTrend() {
  const res = await getMarketHeatTrend({ market: market.value, days: trendDays })
  trendPoints.value = res.data?.points || []
  nextTick(renderTrend)
}

function renderTrend() {
  const xs = trendPoints.value.map(p => p.tradeDate)
  setTrendOption(
    applyChartTheme({
      tooltip: { trigger: 'axis' },
      legend: { data: ['指数%', '热度', '成交额(亿)'], top: 0 },
      grid: { left: 48, right: 24, top: 40, bottom: 28 },
      xAxis: {
        type: 'category',
        data: xs,
        axisLabel: { formatter: v => (v ? String(v).slice(5) : v) }
      },
      yAxis: [
        { type: 'value', name: '指数/热度', scale: true },
        { type: 'value', name: '成交额', splitLine: { show: false } }
      ],
      series: [
        {
          name: '指数%',
          type: 'line',
          smooth: true,
          data: trendPoints.value.map(p => p.indexChangePct),
          itemStyle: { color: '#f56c6c' }
        },
        {
          name: '热度',
          type: 'line',
          smooth: true,
          data: trendPoints.value.map(p => p.heatScore),
          itemStyle: { color: '#e6a23c' },
          areaStyle: { opacity: 0.08 }
        },
        {
          name: '成交额(亿)',
          type: 'bar',
          yAxisIndex: 1,
          data: trendPoints.value.map(p => Math.round((p.totalTurnover || 0) / 1e8)),
          itemStyle: { color: '#409eff', opacity: 0.55 }
        }
      ]
    })
  )
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
    top50.value = (payload.top50 || []).map((r) => ({
      ...r,
      market: normalizeMarket(r.market || market.value)
    }))
    if (payload.tradeDate) tradeDate.value = payload.tradeDate
    await loadTrend()
    syncQuoteSub()
  } finally {
    loading.value = false
  }
}

async function onMarketChange() {
  tradeDate.value = ''
  await Promise.all([loadDates(), loadBoard(false)])
  await loadDaily()
}

async function loadBoard(silent = false) {
  if (!silent) boardLoading.value = true
  try {
    const res = await getBoardQuotes({ market: boardMarket.value || undefined })
    const payload = res.data || {}
    boardRows.value = (payload.rows || payload.quotes || []).map(normalizeQuote)
    syncQuoteSub()
  } catch {
    if (!silent) {
      boardRows.value = []
      syncQuoteSub()
    }
  } finally {
    if (!silent) boardLoading.value = false
  }
}

function normalizeMarket(m) {
  const u = String(m || 'US').trim().toUpperCase()
  if (u === 'HK' || u === 'HKEX') return 'HK'
  if (u === 'CN' || u === 'A' || u === 'SH' || u === 'SZ' || u === 'CSI') return 'CN'
  return 'US'
}

function isIndexRow(row) {
  const cat = String((row && (row.category || row.kind || row.type)) || '').toLowerCase()
  if (cat === 'index') return true
  const sym = String((row && row.symbol) || '')
  return sym.startsWith('^') || sym.startsWith('.')
}

function quotePairsFrom(list, fallbackMarket) {
  const out = []
  for (const row of list || []) {
    if (!row || !row.symbol || isIndexRow(row)) continue
    out.push({ symbol: row.symbol, market: normalizeMarket(row.market || fallbackMarket) })
  }
  return out
}

function dropQuoteSub() {
  if (unsubQuotes) {
    unsubQuotes()
    unsubQuotes = null
  }
}

function applyLiveQuotes(payload) {
  const items = (payload && payload.items) || []
  if (!items.length) return
  top50.value = applyQuotePatch(top50.value, items)
  boardRows.value = applyQuotePatch(boardRows.value, items).map(normalizeQuote)
}

function syncQuoteSub() {
  dropQuoteSub()
  const pairs = [
    ...quotePairsFrom(top50.value, market.value),
    ...quotePairsFrom(boardRows.value, boardMarket.value || market.value)
  ]
  if (!pairs.length) return
  unsubQuotes = getQuotesHub().subscribeQuotes(pairs, applyLiveQuotes)
}

function normalizeQuote(item) {
  const rawPrice = item.last != null ? item.last : item.price
  const price = rawPrice == null ? null : Number(rawPrice)
  const changeRate = item.changePct != null ? item.changePct : (item.changeRate == null ? item.change : item.changeRate)
  const nChange = Number(changeRate)
  const hasChange = changeRate != null && !Number.isNaN(nChange)
  return {
    ...item,
    market: normalizeMarket(item.market || boardMarket.value || market.value),
    price: price == null || Number.isNaN(price) ? null : price.toFixed(2),
    last: price == null || Number.isNaN(price) ? item.last : price,
    changeRate: hasChange ? nChange : Number(changeRate),
    changePct: hasChange ? nChange : item.changePct,
    changeText: hasChange
      ? `${nChange >= 0 ? '+' : ''}${nChange.toFixed(2)}%`
      : (item.changeText || '--'),
    up: hasChange ? nChange >= 0 : (item.up == null ? nChange >= 0 : !!item.up)
  }
}

const boardStale = computed(() => boardRows.value.length === 0)

/** 刷新按钮：热度 + 报价 + 指数条一起刷 */
async function refreshAll(fromUser = false) {
  await Promise.all([loadDaily(), loadBoard(!fromUser), indexStripRef.value?.loadQuotes()])
}

// ---- 跳转 ----
function withMarketQuery(row) {
  return { symbol: row.symbol, market: marketLabelKey(row) }
}
function marketLabelKey(row) {
  const m = String(row.market || market.value || 'CN').toUpperCase()
  return m === 'A' ? 'CN' : m === 'SH' || m === 'SZ' ? 'CN' : m
}
function goSymbol(row) {
  router.push({ path: '/market/symbol', query: withMarketQuery(row) })
}
function goKline(row) {
  router.push({ path: '/market/kline', query: withMarketQuery(row) })
}
function goAi(row) {
  router.push({ path: '/market/ai-workbench', query: withMarketQuery(row) })
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: marketLabelKey(row), groups: 'Top50' })
    row.inWatchlist = true
  } finally {
    adding.value = ''
  }
}

function stopQuoteTimer() {
  if (quoteTimer) {
    clearInterval(quoteTimer)
    quoteTimer = null
  }
}
function startQuoteTimer() {
  stopQuoteTimer()
  quoteTimer = setInterval(() => loadBoard(true), 60000)
}
function handleVisibility() {
  if (document.visibilityState === 'visible') {
    if (!quoteTimer) startQuoteTimer()
    syncQuoteSub()
  } else {
    stopQuoteTimer()
    dropQuoteSub()
  }
}

onMounted(async () => {
  // 工作台三市场卡片深链：?market=US/HK/CN
  const qm = String(route.query.market || '').toUpperCase()
  if (['US', 'HK', 'CN'].includes(qm)) market.value = qm
  await loadDates()
  await loadDaily()
  loadBoard(false)
  startQuoteTimer()
  document.addEventListener('visibilitychange', handleVisibility)
})
onActivated(() => {
  startQuoteTimer()
  if (!boardRows.value.length && !top50.value.length) loadBoard(true)
  else syncQuoteSub()
})
onDeactivated(() => {
  stopQuoteTimer()
  dropQuoteSub()
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibility)
  stopQuoteTimer()
  dropQuoteSub()
  disposeTrend()
})
</script>

<style scoped lang="scss">
.market-center {
  --mc-up: var(--stat-up, #dc2626);
  --mc-down: var(--stat-down, #059669);
}

.mb16 {
  margin-bottom: 14px;
}

.block-gap {
  margin-bottom: 14px;
}

.mono {
  font-family:
    'SF Mono',
    Menlo,
    Consolas,
    monospace;
  font-size: 13px;
}

/* ---- 渐变 Hero（对标工作台 HeroBar）---- */
.hero-card {
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

  .hero-title {
    font-size: 22px;
    font-weight: 700;
  }

  .hero-sub {
    margin-top: 4px;
    font-size: 13px;
    opacity: 0.88;
    display: flex;
    align-items: center;
    gap: 8px;

    .asof-tag {
      border: none;
      background: rgba(255, 255, 255, 0.18);
      color: #fff;
    }
  }

  .hero-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
  }

  /* Element 单选钮在渐变底上改为玻璃片样式 */
  .market-switch {
    :deep(.el-radio-button__inner) {
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.35);
      color: #fff;
      box-shadow: none;
    }

    :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
      background: rgba(255, 255, 255, 0.92);
      color: #4f46e5;
      font-weight: 600;
    }
  }
}

/* ---- 统计四卡（对标工作台 AssetStrip）---- */
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  margin-bottom: 10px;
  border-radius: 14px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: default;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-glow);
  }

  .stat-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 20px;
    flex-shrink: 0;

    &.icon-index {
      background: linear-gradient(135deg, #4f46e5, #6366f1);
    }

    &.icon-turnover {
      background: linear-gradient(135deg, #0ea5e9, #38bdf8);
    }

    &.icon-breadth {
      background: linear-gradient(135deg, #f59e0b, #fbbf24);
    }

    &.icon-score {
      background: linear-gradient(135deg, #ec4899, #f472b6);
    }
  }

  .stat-label {
    color: var(--text-muted, #909399);
    font-size: 12px;
  }

  .stat-value {
    font-size: 21px;
    font-weight: 700;
    line-height: 1.35;
    color: var(--text-emphasis, #303133);

    &.up {
      color: var(--mc-up);
    }

    &.down {
      color: var(--mc-down);
    }
  }

  .stat-sub {
    font-size: 11px;
    color: var(--text-muted, #909399);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

/* ---- 面板卡 ---- */
.panel-card {
  border-radius: 14px;
  border: 1px solid var(--border-soft, #eef2ff);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;

  .panel-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-emphasis, #303133);
  }

  .panel-sub {
    font-size: 12px;
    color: var(--text-muted, #909399);
  }

  .table-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
}

.summary {
  margin: 0;
  line-height: 1.8;
  color: var(--text-emphasis, #303133);
}

.trend-chart {
  height: 260px;
  width: 100%;
}

.chg-cell {
  font-weight: 600;
  font-variant-numeric: tabular-nums;

  &.up {
    color: var(--mc-up);
  }

  &.down {
    color: var(--mc-down);
  }
}

.live-dot-wrap {
  display: inline-flex;
  align-items: center;
  gap: 5px;

  .live-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #34d399;
    box-shadow: 0 0 6px rgba(52, 211, 153, 0.9);
    animation: pulse 2s infinite;
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.45;
  }
}

@media (max-width: 768px) {
  .hero-card {
    padding: 16px 18px;
  }
}
</style>
