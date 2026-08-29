<template>
  <div class="app-container watch-page">
    <div class="page-hero">
      <div>
        <h2>自选清单</h2>
        <p>按登录账号隔离。左侧按分组筛选，最新价走实时通道，中间看图，右侧看详情与分析。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['market:watchlist:add']">新增自选</el-button>
        <el-button type="success" icon="MagicStick" :loading="analyzeAllLoading" @click="handleAnalyzeAll" v-hasPermi="['market:watchlist:analyze']">立即分析全部</el-button>
        <el-button :loading="backtestLoading" @click="loadBacktest">建议回测</el-button>
        <el-button icon="Refresh" :loading="loading" @click="loadOverview">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="overview.aiHint"
      :title="overview.aiHint"
      type="warning"
      show-icon
      class="mb16"
      :closable="false"
    />

    <el-row :gutter="16" class="mb16">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.label">
        <div class="stat-card" :class="card.tone">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card v-if="backtest.count != null" shadow="never" class="panel mb16" v-loading="backtestLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">建议回测（1/5 日）</span>
          <span class="panel-sub">{{ backtest.message || '买入/加仓为多，减仓/卖出为空' }}</span>
        </div>
      </template>
      <el-row :gutter="12" class="mb16">
        <el-col :xs="12" :sm="6" v-for="card in backtestCards" :key="card.label">
          <div class="mini-stat">
            <div class="mini-label">{{ card.label }}</div>
            <div class="mini-value">{{ card.value }}</div>
          </div>
        </el-col>
      </el-row>
      <el-table :data="backtest.items || []" size="small" max-height="280">
        <el-table-column prop="analysisTime" label="分析时间" width="160" />
        <el-table-column prop="symbol" label="标的" width="100" />
        <el-table-column prop="recommendation" label="建议" width="80" />
        <el-table-column label="1日收益" width="100" align="right">
          <template #default="scope">{{ formatPct(scope.row.fwd1) }}</template>
        </el-table-column>
        <el-table-column label="5日收益" width="100" align="right">
          <template #default="scope">{{ formatPct(scope.row.fwd5) }}</template>
        </el-table-column>
        <el-table-column label="1日方向" width="90" align="center">
          <template #default="scope">{{ hitLabel(scope.row.hit1) }}</template>
        </el-table-column>
        <el-table-column label="5日方向" width="90" align="center">
          <template #default="scope">{{ hitLabel(scope.row.hit5) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!(backtest.items || []).length && !backtestLoading" description="暂无买入/卖出类建议，分析后再回测" :image-size="56" />
    </el-card>

    <el-card shadow="never" class="panel mb16" v-loading="corrLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">自选相关热力</span>
          <span class="panel-sub">{{ corr.message || '日收益 Pearson，红=同向 青=对冲' }}</span>
        </div>
      </template>
      <div ref="corrRef" class="corr-chart" v-show="(corr.symbols || []).length >= 2" />
      <el-empty v-if="(corr.symbols || []).length < 2 && !corrLoading" :description="corr.message || '至少两只有日K的自选'" :image-size="56" />
    </el-card>

    <div class="watch-shell" v-loading="loading">
      <aside class="col-left">
        <div class="group-bar">
          <button
            type="button"
            class="group-chip"
            :class="{ active: activeGroup === '' }"
            @click="activeGroup = ''"
          >全部 {{ items.length }}</button>
          <button
            v-for="g in groups"
            :key="g.name"
            type="button"
            class="group-chip"
            :class="{ active: activeGroup === g.name }"
            @click="activeGroup = g.name"
          >{{ g.name }} {{ g.count }}</button>
        </div>
        <el-input v-model="keyword" clearable size="small" placeholder="搜索代码/名称" class="mb8" />
        <el-scrollbar class="sym-scroll">
          <div
            v-for="row in filteredItems"
            :key="row.id"
            class="sym-row"
            :class="{ active: current && current.id === row.id }"
            @click="selectRow(row)"
          >
            <div class="sym-cell">
              <strong>{{ row.symbol }}</strong>
              <span>{{ row.name || '--' }}</span>
            </div>
            <div class="sym-quote">
              <span>{{ formatNum(row.last) }}</span>
              <span :class="chgClass(row.changeRate)">{{ formatPct(row.changeRate) }}</span>
            </div>
          </div>
          <el-empty v-if="!filteredItems.length" description="当前分组没有标的" :image-size="56" />
        </el-scrollbar>
      </aside>

      <section class="col-mid">
        <div class="mid-head" v-if="current">
          <div>
            <strong>{{ current.name || current.symbol }}</strong>
            <span class="muted">{{ current.symbol }} · {{ marketLabel(current.market) }}</span>
          </div>
          <div class="mid-acts">
            <el-radio-group v-model="period" size="small" @change="loadChart">
              <el-radio-button label="daily">日K</el-radio-button>
              <el-radio-button label="weekly">周K</el-radio-button>
              <el-radio-button label="monthly">月K</el-radio-button>
            </el-radio-group>
            <el-button link type="primary" @click="openSymbol(current)">详情</el-button>
            <el-button link type="success" :loading="analyzingId === current.id" @click="handleAnalyzeOne(current)" v-hasPermi="['market:watchlist:analyze']">分析</el-button>
            <el-button link type="danger" @click="handleDelete(current)" v-hasPermi="['market:watchlist:remove']">移除</el-button>
          </div>
        </div>
        <div ref="chartRef" class="kline-chart" v-show="current" v-loading="chartLoading" />
        <el-empty v-if="!current" description="选择左侧一只自选股查看走势" :image-size="72" />
      </section>

      <aside class="col-right" v-if="showDetailPane">
        <el-card shadow="never" class="panel" v-if="current">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">详情</span>
              <el-tag v-if="current.recommendation" size="small" :type="recType(current.recommendation)" effect="dark">{{ current.recommendation }}</el-tag>
            </div>
          </template>
          <div class="quote-line">
            <b :class="chgClass(current.changeRate)">{{ formatNum(current.last) }}</b>
            <span :class="chgClass(current.changeRate)">{{ formatPct(current.changeRate) }}</span>
          </div>
          <div class="meta-grid">
            <div><span>市场</span><b>{{ marketLabel(current.market) }}</b></div>
            <div><span>分组</span><b>{{ (current.groups || []).join('、') || '未分组' }}</b></div>
            <div><span>备注</span><b>{{ current.note || '--' }}</b></div>
            <div><span>分析</span><b>{{ current.analysisTime || '尚未分析' }}</b></div>
          </div>
          <div class="row-acts">
            <el-button link type="primary" @click="openSymbol(current)">标的详情</el-button>
            <el-button link type="success" :loading="analyzingId === current.id" @click="handleAnalyzeOne(current)" v-hasPermi="['market:watchlist:analyze']">分析</el-button>
            <el-button link type="danger" @click="handleDelete(current)" v-hasPermi="['market:watchlist:remove']">移除</el-button>
          </div>
          <div class="advice-block">
            <p class="advice-summary">{{ current.summary || '暂无分析摘要，请点「分析」。' }}</p>
          </div>
          <el-tabs v-model="activeTab">
            <el-tab-pane label="建议" name="advice">
              <p class="tab-body">{{ (current.analysis && current.analysis.operationAdvice) || '暂无' }}</p>
              <p class="risk" v-if="current.analysis && current.analysis.riskWarning">风险：{{ current.analysis.riskWarning }}</p>
            </el-tab-pane>
            <el-tab-pane label="指标" name="indicator">
              <p class="tab-body">{{ (current.analysis && current.analysis.indicatorReview) || '暂无' }}</p>
            </el-tab-pane>
            <el-tab-pane label="资讯" name="news">
              <p class="tab-body">{{ (current.analysis && current.analysis.newsReview) || '暂无' }}</p>
            </el-tab-pane>
            <el-tab-pane label="舆情" name="sentiment">
              <p class="tab-body">{{ (current.analysis && current.analysis.sentimentReview) || '暂无' }}</p>
            </el-tab-pane>
          </el-tabs>
          <div class="hist-block">
            <div class="hist-title">分析历史</div>
            <div v-show="historySeries.length" ref="histRef" class="hist-chart"></div>
            <el-empty v-if="!historySeries.length" description="暂无历史" :image-size="40" />
          </div>
        </el-card>
        <el-card shadow="never" class="panel" v-else>
          <el-empty description="选择左侧一只自选股查看详情" :image-size="64" />
        </el-card>
      </aside>
    </div>

    <el-dialog title="新增自选" v-model="open" width="480px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="市场" prop="market">
          <el-select v-model="form.market" style="width: 100%">
            <el-option label="美股 US" value="US" />
            <el-option label="港股 HK" value="HK" />
            <el-option label="A股 CN" value="CN" />
          </el-select>
        </el-form-item>
        <el-form-item label="标的" prop="symbolKey">
          <el-select
            v-model="form.symbolKey"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入代码，如 AAPL / 0700.HK / 600519"
            style="width: 100%"
            @change="onSymbolChange"
          >
            <el-option v-for="it in instruments" :key="it.symbol + it.market" :label="`${it.name} (${it.symbol})`" :value="it.symbol + '|' + it.market" />
          </el-select>
        </el-form-item>
        <el-form-item label="分组" prop="groups">
          <el-input v-model="form.groups" placeholder="分组名，多个用逗号，如 七巨头,持仓" />
        </el-form-item>
        <el-form-item label="备注" prop="note">
          <el-input v-model="form.note" placeholder="可选备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="submitLoading" @click="submitForm">确 定</el-button>
        <el-button @click="open = false">取 消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="MarketWatchlist">
import { useEChart } from '@/composables/useEChart'
import { applyQuotePatch, getQuotesHub } from '@/composables/useMarketQuotesWs'
import {
  getMarketWatchlistOverview,
  addMarketWatchlist,
  delMarketWatchlist,
  analyzeMarketWatchlist,
  getMarketWatchlistAnalysis,
  getMarketWatchlistBacktest,
  getWatchlistCorrelation,
  listInstrument,
  getKline,
  pollMarketJob
} from '@/api/market'

const { proxy } = getCurrentInstance()
const router = useRouter()

const loading = ref(false)
const analyzeAllLoading = ref(false)
const analyzingId = ref(null)
const overview = ref({ items: [], count: 0, bullish: 0, bearish: 0, neutral: 0, lastAnalysisTime: null, aiHint: null })
const historySeries = ref([])
const histRef = ref(null)
const { setOption: setHistOption, dispose: disposeHist } = useEChart(histRef)
const items = computed(() => overview.value.items || [])
const groups = computed(() => overview.value.groups || [])
const activeGroup = ref('')
const keyword = ref('')
const period = ref('daily')
const chartLoading = ref(false)
const chartRef = ref(null)
const { setOption: setChartOption, dispose: disposeChart } = useEChart(chartRef)
const viewportWidth = ref(typeof window === 'undefined' ? 1440 : window.innerWidth)
const showDetailPane = computed(() => viewportWidth.value >= 1100)
const filteredItems = computed(() => {
  const kw = (keyword.value || '').trim().toLowerCase()
  return items.value.filter(row => {
    const groupOk = !activeGroup.value || (row.groups || []).includes(activeGroup.value)
    if (!groupOk) return false
    if (!kw) return true
    return `${row.symbol} ${row.name || ''} ${row.note || ''}`.toLowerCase().includes(kw)
  })
})
const current = ref(null)
const activeTab = ref('advice')
const instruments = ref([])
const open = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const form = ref({ symbolKey: '', symbol: '', market: 'US', groups: '', note: '' })
const rules = { symbolKey: [{ required: true, message: '请选择或输入标的', trigger: 'change' }] }
const backtest = ref({})
const backtestLoading = ref(false)
const corr = ref({ symbols: [], names: [], matrix: [], message: '' })
const corrLoading = ref(false)
const corrRef = ref(null)
const { setOption: setCorrOption } = useEChart(corrRef)
let quoteTimer = null
let unsubQuotes = null

const statCards = computed(() => [
  { label: '自选数量', value: overview.value.count || 0, tone: 't-blue' },
  { label: '偏多', value: overview.value.bullish || 0, tone: 't-green' },
  { label: '偏空', value: overview.value.bearish || 0, tone: 't-red' },
  { label: '中性', value: overview.value.neutral || 0, tone: 't-gray' }
])
const backtestCards = computed(() => [
  { label: '可计样本', value: backtest.value.scoredCount || 0 },
  { label: '1日命中率', value: formatHitRate(backtest.value.hitRate1) },
  { label: '5日命中率', value: formatHitRate(backtest.value.hitRate5) },
  { label: '方向收益(1/5日)', value: `${formatPct(backtest.value.avgSigned1)} / ${formatPct(backtest.value.avgSigned5)}` }
])

function marketLabel(market) {
  const map = { US: '美股', HK: '港股', CN: 'A股', A: 'A股' }
  return map[String(market || '').toUpperCase()] || market || ''
}
function formatNum(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  return Number.isNaN(n) ? v : n.toFixed(2)
}
function formatPct(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (Number.isNaN(n)) return '--'
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}
function chgClass(v) {
  const n = Number(v)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}
function formatHitRate(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (Number.isNaN(n)) return '--'
  return (n * 100).toFixed(1) + '%'
}
function hitLabel(v) {
  if (v === true) return '命中'
  if (v === false) return '未中'
  return '待观察'
}
function recType(rec) {
  if (['买入', '加仓'].includes(rec)) return 'danger'
  if (['卖出', '减仓'].includes(rec)) return 'success'
  if (rec === '持有') return 'warning'
  return 'info'
}

function selectRow(row) {
  current.value = row
  activeTab.value = 'advice'
  loadHistory(row)
  loadChart()
}

async function loadChart() {
  if (!current.value || !chartRef.value) return
  chartLoading.value = true
  try {
    const res = await getKline({
      symbol: current.value.symbol,
      market: current.value.market || 'US',
      period: period.value
    })
    const rows = (res.data && (res.data.klines || res.data.rows)) || res.rows || []
    const dates = rows.map(d => d.date)
    const ohlc = rows.map(d => [d.open, d.close, d.low, d.high])
    setChartOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 16, top: 16, bottom: 28 },
      xAxis: { type: 'category', data: dates, axisLabel: { formatter: v => String(v).slice(5) } },
      yAxis: { type: 'value', scale: true, splitNumber: 4 },
      series: [{ type: 'candlestick', data: ohlc, itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' } }]
    }, true)
  } catch {
    setChartOption({ series: [] }, true)
  } finally {
    chartLoading.value = false
  }
}

function loadHistory(row) {
  if (!row || !row.symbol) {
    historySeries.value = []
    return
  }
  getMarketWatchlistAnalysis({ symbol: row.symbol, market: row.market || 'US', limit: 24 }).then(res => {
    const data = res.data || {}
    historySeries.value = data.series || []
    nextTick(renderHistory)
  }).catch(() => {
    historySeries.value = []
  })
}

function renderHistory() {
  if (!histRef.value) return
  const series = historySeries.value
  setHistOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 12, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: series.map(s => (s.time || '').slice(5, 16)), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 100, splitNumber: 4 },
    series: [{ type: 'line', data: series.map(s => s.confidence), smooth: true, symbol: 'circle', areaStyle: { opacity: 0.12 } }]
  }, true)
}

function openSymbol(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } })
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await getMarketWatchlistOverview()
    overview.value = res.data || { items: [] }
    const rows = overview.value.items || []
    if (current.value) {
      const hit = rows.find(r => r.id === current.value.id)
      current.value = hit || rows[0] || null
    } else {
      current.value = rows[0] || null
    }
    if (current.value) {
      loadHistory(current.value)
      nextTick(loadChart)
    }
    syncQuoteSub()
    loadCorrelation()
  } finally {
    loading.value = false
  }
}

async function loadCorrelation() {
  corrLoading.value = true
  try {
    const res = await getWatchlistCorrelation({ days: 60, limit: 12 })
    corr.value = res.data || { symbols: [], matrix: [] }
    await nextTick()
    renderCorr()
  } catch {
    corr.value = { symbols: [], names: [], matrix: [], message: '相关矩阵暂不可用' }
  } finally {
    corrLoading.value = false
  }
}

function renderCorr() {
  const symbols = corr.value.symbols || []
  const names = corr.value.names || symbols
  const matrix = corr.value.matrix || []
  if (symbols.length < 2) return
  const labels = names.map((n, i) => n || symbols[i])
  const data = []
  matrix.forEach((row, i) => {
    (row || []).forEach((v, j) => {
      if (v == null) return
      data.push([j, i, Number(v.toFixed ? v.toFixed(2) : v)])
    })
  })
  setCorrOption({
    tooltip: { formatter: (p) => `${labels[p.value[1]]} × ${labels[p.value[0]]}: ${p.value[2]}` },
    grid: { left: 72, right: 24, top: 16, bottom: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 40, fontSize: 11 } },
    yAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    visualMap: {
      min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
      inRange: { color: ['#26a69a', '#f8fafc', '#ef5350'] }
    },
    series: [{ type: 'heatmap', data, label: { show: symbols.length <= 8, formatter: (p) => p.value[2] } }]
  })
}

function loadInstruments() {
  listInstrument().then(res => {
    instruments.value = res.data || res.rows || []
  })
}

function handleAdd() {
  form.value = { symbolKey: '', symbol: '', market: 'US', groups: '', note: '' }
  open.value = true
  nextTick(() => formRef.value && formRef.value.clearValidate())
}

function onSymbolChange(val) {
  if (!val) return
  if (val.includes('|')) {
    const [symbol, market] = val.split('|')
    form.value.symbol = String(symbol || '').toUpperCase()
    if (market) form.value.market = market
    return
  }
  form.value.symbol = String(val).trim().toUpperCase()
}

function submitForm() {
  formRef.value.validate(valid => {
    if (!valid) return
    submitLoading.value = true
    addMarketWatchlist({
      symbol: form.value.symbol || String(form.value.symbolKey || '').split('|')[0],
      market: form.value.market,
      groups: form.value.groups,
      note: form.value.note
    })
      .then(() => {
        proxy.$modal.msgSuccess('新增成功')
        open.value = false
        loadOverview()
      })
      .finally(() => {
        submitLoading.value = false
      })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`确认将 ${row.symbol} 移出自选清单？`).then(() => {
    return delMarketWatchlist(row.id)
  }).then(() => {
    proxy.$modal.msgSuccess('已删除')
    if (current.value && current.value.id === row.id) current.value = null
    loadOverview()
  }).catch(() => {})
}

async function handleAnalyzeOne(row) {
  analyzingId.value = row.id
  try {
    const res = await analyzeMarketWatchlist({ symbol: row.symbol, market: row.market, refreshContent: true })
    const d = res.data || {}
    if (d.accepted || d.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队')
      if (d.jobId) {
        const ticket = await pollMarketJob(d.jobId)
        if (ticket.status === 'failed') {
          proxy.$modal.msgError(ticket.error || '分析失败')
          return
        }
      }
      await loadOverview()
      return
    }
    proxy.$modal.msgSuccess(res.msg || '分析完成')
    await loadOverview()
  } finally {
    analyzingId.value = null
  }
}

async function handleAnalyzeAll() {
  if (!items.value.length) {
    proxy.$modal.msgWarning('请先添加自选股')
    return
  }
  analyzeAllLoading.value = true
  try {
    const res = await analyzeMarketWatchlist({ refreshContent: true })
    const d = res.data || {}
    if (d.accepted || d.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已加入后台队列')
      if (d.jobId) {
        const ticket = await pollMarketJob(d.jobId)
        if (ticket.status === 'failed') {
          proxy.$modal.msgError(ticket.error || '分析失败')
          return
        }
      }
      await loadOverview()
      return
    }
    proxy.$modal.msgSuccess(res.msg || '分析完成')
    await loadOverview()
  } finally {
    analyzeAllLoading.value = false
  }
}

async function loadBacktest() {
  backtestLoading.value = true
  try {
    const res = await getMarketWatchlistBacktest({ limit: 200 })
    backtest.value = res.data || {}
  } finally {
    backtestLoading.value = false
  }
}

function applyLiveQuotes(payload) {
  const items = applyQuotePatch(overview.value.items || [], (payload && payload.items) || [])
  overview.value = { ...overview.value, items, quoteSource: 'live' }
  if (current.value) {
    const hit = items.find(r => r.id === current.value.id)
    if (hit) current.value = hit
  }
}

function syncQuoteSub() {
  if (unsubQuotes) {
    unsubQuotes()
    unsubQuotes = null
  }
  const pairs = (overview.value.items || []).map(row => ({ symbol: row.symbol, market: row.market }))
  if (!pairs.length) return
  unsubQuotes = getQuotesHub().subscribeQuotes(pairs, applyLiveQuotes)
}

async function loadOverviewQuiet() {
  try {
    const res = await getMarketWatchlistOverview()
    const data = res.data || { items: [] }
    overview.value = data
    const rows = data.items || []
    if (current.value) {
      const hit = rows.find(r => r.id === current.value.id)
      if (hit) current.value = hit
    }
    syncQuoteSub()
  } catch {
    /* ignore live poll errors */
  }
}

function onResize() {
  viewportWidth.value = window.innerWidth
}

function stopQuoteTimer() {
  if (quoteTimer) {
    clearInterval(quoteTimer)
    quoteTimer = null
  }
}
function startQuoteTimer() {
  stopQuoteTimer()
  quoteTimer = setInterval(loadOverviewQuiet, 60000)
}
function handleVisibility() {
  if (document.visibilityState === 'visible') {
    if (!quoteTimer) {
      loadOverviewQuiet()
      startQuoteTimer()
    }
  } else {
    stopQuoteTimer()
    if (unsubQuotes) {
      unsubQuotes()
      unsubQuotes = null
    }
  }
}

onMounted(() => {
  loadInstruments()
  loadOverview()
  loadBacktest()
  startQuoteTimer()
  window.addEventListener('resize', onResize)
  document.addEventListener('visibilitychange', handleVisibility)
})
onActivated(() => {
  loadOverviewQuiet()
  startQuoteTimer()
})
onDeactivated(() => {
  stopQuoteTimer()
  if (unsubQuotes) {
    unsubQuotes()
    unsubQuotes = null
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibility)
  stopQuoteTimer()
  if (unsubQuotes) unsubQuotes()
  window.removeEventListener('resize', onResize)
  disposeHist()
  disposeChart()
})
</script>

<style scoped lang="scss">
.page-hero {
  display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: #909399; font-size: 13px; max-width: 640px; }
}
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.mb16 { margin-bottom: 16px; }
.stat-card {
  border-radius: 14px; padding: 14px 16px; color: #fff; margin-bottom: 12px;
  .stat-label { font-size: 12px; opacity: 0.85; }
  .stat-value { font-size: 24px; font-weight: 700; margin-top: 4px; }
  &.t-blue { background: linear-gradient(135deg, #6366f1, #8b5cf6); }
  &.t-green { background: linear-gradient(135deg, #10b981, #34d399); }
  &.t-red { background: linear-gradient(135deg, #ef4444, #f87171); }
  &.t-gray { background: linear-gradient(135deg, #64748b, #94a3b8); }
}
.panel { border-radius: 14px; margin-bottom: 16px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.panel-title { font-weight: 600; }
.panel-sub { font-size: 12px; color: #909399; }
.sym-cell { display: flex; flex-direction: column; line-height: 1.4;
  strong { font-size: 14px; }
  span { font-size: 12px; color: #909399; }
}
.up { color: #ef4444; font-weight: 600; }
.down { color: #10b981; font-weight: 600; }
.muted { color: #94a3b8; font-size: 12px; }
.advice-block { margin-bottom: 8px; }
.advice-meta { display: flex; gap: 12px; font-size: 12px; color: #64748b; margin-bottom: 8px; flex-wrap: wrap; }
.advice-summary { margin: 0; line-height: 1.7; color: #334155; }
.tab-body { margin: 0; line-height: 1.8; color: #475569; white-space: pre-wrap; }
.risk { margin-top: 10px; color: #b45309; font-size: 13px; }
.drawer-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.src-tag { margin-left: 6px; }
.hist-block { margin-top: 12px; }
.hist-title { font-weight: 600; margin-bottom: 6px; }
.hist-chart { height: 160px; }
.mini-stat { background: var(--surface-card, #f8fafc); border: 1px solid var(--border-soft, #e5e7eb); border-radius: 12px; padding: 12px; margin-bottom: 8px; }
.mini-label { font-size: 12px; color: #909399; }
.mini-value { font-size: 18px; font-weight: 700; margin-top: 4px; }
.watch-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1.35fr) minmax(300px, 0.9fr);
  gap: 12px;
  min-height: 620px;
  align-items: stretch;
}
.col-left, .col-mid, .col-right { min-width: 0; }
.col-left, .col-mid {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 12px;
}
.group-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.group-chip {
  border: 1px solid var(--el-border-color); background: transparent; border-radius: 999px;
  padding: 2px 10px; font-size: 12px; cursor: pointer; color: inherit;
}
.group-chip.active { background: #6366f1; border-color: #6366f1; color: #fff; }
.mb8 { margin-bottom: 8px; }
.sym-scroll { height: 520px; }
.sym-row {
  display: flex; justify-content: space-between; gap: 8px; padding: 8px 6px;
  border-radius: 8px; cursor: pointer;
}
.sym-row:hover, .sym-row.active { background: var(--el-fill-color-light); }
.sym-quote { text-align: right; font-size: 12px; display: flex; flex-direction: column; }
.mid-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.mid-acts { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.kline-chart { height: 520px; }
.quote-line { display: flex; gap: 10px; align-items: baseline; margin-bottom: 10px; b { font-size: 22px; } }
.meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;
  span { display: block; font-size: 12px; color: #909399; }
  b { font-size: 13px; font-weight: 600; }
}
.row-acts { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.corr-chart { height: 320px; width: 100%; }

@media (max-width: 1100px) {
  .watch-shell { grid-template-columns: 240px minmax(0, 1fr); }
  .col-right { display: none; }
}
</style>
