<template>
  <div class="app-container watch-page">
    <div class="page-hero">
      <div>
        <h2>自选清单</h2>
        <p>关注自选股的价格、技术指标、长桥资讯与舆情。系统每小时综合分析一次并给出建议。</p>
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

    <el-row :gutter="16">
      <el-col :xs="24" :lg="15">
        <el-card shadow="never" class="panel" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">关注标的</span>
              <span class="panel-sub">最近分析 {{ overview.lastAnalysisTime || '尚未运行' }}</span>
            </div>
          </template>
          <el-table :data="items" highlight-current-row @row-click="selectRow">
            <el-table-column label="标的" min-width="160">
              <template #default="scope">
                <div class="sym-cell">
                  <strong>{{ scope.row.symbol }}</strong>
                  <span>{{ scope.row.name || '--' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="市场" prop="market" width="70" align="center">
              <template #default="scope">{{ marketLabel(scope.row.market) }}</template>
            </el-table-column>
            <el-table-column label="最新价" width="130" align="right">
              <template #default="scope">
                <span>{{ formatNum(scope.row.last) }}</span>
                <el-tag v-if="scope.row.quoteSource === 'longbridge'" size="small" type="success" effect="plain" class="src-tag">实时</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="涨跌" width="100" align="right">
              <template #default="scope">
                <span :class="chgClass(scope.row.changeRate)">{{ formatPct(scope.row.changeRate) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="建议" width="90" align="center">
              <template #default="scope">
                <el-tag v-if="scope.row.recommendation" size="small" :type="recType(scope.row.recommendation)" effect="dark">
                  {{ scope.row.recommendation }}
                </el-tag>
                <span v-else class="muted">待分析</span>
              </template>
            </el-table-column>
            <el-table-column label="立场" width="80" align="center">
              <template #default="scope">{{ scope.row.stance || '--' }}</template>
            </el-table-column>
            <el-table-column label="置信度" width="80" align="center">
              <template #default="scope">{{ scope.row.confidence != null ? scope.row.confidence : '--' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="center">
              <template #default="scope">
                <el-button link type="primary" @click.stop="openSymbol(scope.row)">详情</el-button>
                <el-button link type="success" :loading="analyzingId === scope.row.id" @click.stop="handleAnalyzeOne(scope.row)" v-hasPermi="['market:watchlist:analyze']">分析</el-button>
                <el-button link type="danger" @click.stop="handleDelete(scope.row)" v-hasPermi="['market:watchlist:remove']">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!items.length && !loading" description="还没有自选股，点击「新增自选」开始关注" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="9">
        <el-card shadow="never" class="panel" v-if="current">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">{{ current.symbol }} {{ current.name || '' }}</span>
              <el-tag v-if="current.recommendation" size="small" :type="recType(current.recommendation)" effect="dark">{{ current.recommendation }}</el-tag>
            </div>
          </template>
          <div class="advice-block">
            <div class="advice-meta">
              <span>立场 {{ current.stance || '--' }}</span>
              <span>置信度 {{ current.confidence != null ? current.confidence : '--' }}</span>
              <span>{{ current.source === 'rule' ? '指标兜底' : (current.source === 'ai' ? 'AI 综合' : '未分析') }}</span>
            </div>
            <p class="advice-summary">{{ current.summary || '暂无分析摘要，请点击「分析」。' }}</p>
          </div>
          <el-tabs v-model="activeTab">
            <el-tab-pane label="操作建议" name="advice">
              <p class="tab-body">{{ (current.analysis && current.analysis.operationAdvice) || '暂无' }}</p>
              <p class="risk" v-if="current.analysis && current.analysis.riskWarning">风险：{{ current.analysis.riskWarning }}</p>
            </el-tab-pane>
            <el-tab-pane label="技术指标" name="indicator">
              <p class="tab-body">{{ (current.analysis && current.analysis.indicatorReview) || '暂无指标解读' }}</p>
            </el-tab-pane>
            <el-tab-pane label="长桥资讯" name="news">
              <p class="tab-body">{{ (current.analysis && current.analysis.newsReview) || '暂无资讯解读' }}</p>
            </el-tab-pane>
            <el-tab-pane label="舆情" name="sentiment">
              <p class="tab-body">{{ (current.analysis && current.analysis.sentimentReview) || '暂无舆情解读' }}</p>
            </el-tab-pane>
          </el-tabs>
          <div class="hist-block">
            <div class="hist-title">分析历史</div>
            <div v-show="historySeries.length" ref="histRef" class="hist-chart"></div>
            <el-empty v-if="!historySeries.length" description="暂无历史，分析后可看置信度变化" :image-size="48" />
          </div>
          <div class="drawer-foot">
            <span class="muted">{{ current.analysisTime || '尚未分析' }}</span>
            <el-button link type="primary" @click="openSymbol(current)">打开标的详情</el-button>
          </div>
        </el-card>
        <el-card shadow="never" class="panel" v-else>
          <el-empty description="选择左侧一只自选股查看综合建议" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

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
        <el-form-item label="备注" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="3" placeholder="可选备注，例如持仓理由" />
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
import {
  getMarketWatchlistOverview,
  addMarketWatchlist,
  delMarketWatchlist,
  analyzeMarketWatchlist,
  getMarketWatchlistAnalysis,
  getMarketWatchlistBacktest,
  listInstrument
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
const current = ref(null)
const activeTab = ref('advice')
const instruments = ref([])
const open = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const form = ref({ symbolKey: '', symbol: '', market: 'US', note: '' })
const rules = { symbolKey: [{ required: true, message: '请选择或输入标的', trigger: 'change' }] }
const backtest = ref({})
const backtestLoading = ref(false)
let quoteTimer = null

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
    if (current.value) loadHistory(current.value)
  } finally {
    loading.value = false
  }
}

function loadInstruments() {
  listInstrument().then(res => {
    instruments.value = res.data || res.rows || []
  })
}

function handleAdd() {
  form.value = { symbolKey: '', symbol: '', market: 'US', note: '' }
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
    proxy.$modal.msgSuccess(res.msg || (d.accepted ? '已加入后台队列' : '分析完成'))
    if (!d.accepted) await loadOverview()
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
  } catch {
    /* ignore live poll errors */
  }
}

onMounted(() => {
  loadInstruments()
  loadOverview()
  loadBacktest()
  quoteTimer = setInterval(loadOverviewQuiet, 8000)
})
onBeforeUnmount(() => {
  if (quoteTimer) clearInterval(quoteTimer)
  disposeHist()
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
</style>
