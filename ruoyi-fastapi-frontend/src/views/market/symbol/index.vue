<template>
  <div class="app-container symbol-detail" v-loading="coreLoading">
    <div class="top-bar">
      <el-button icon="ArrowLeft" text @click="goBack">返回</el-button>
      <el-select v-model="symbolKey" filterable style="width: 280px" @change="onSymbolChange">
        <el-option
          v-for="it in instruments"
          :key="it.symbol + it.market"
          :label="`${it.name} (${it.symbol})`"
          :value="it.symbol + '|' + it.market"
        />
      </el-select>
      <el-button type="primary" plain icon="Refresh" :loading="coreLoading" @click="loadAll">刷新</el-button>
    </div>

    <!-- Hero -->
    <el-card shadow="never" class="panel mb16">
      <div class="hero">
        <div class="hero-main">
          <div class="hero-code">{{ overview.symbol || symbol }}</div>
          <div class="hero-name">{{ overview.name || '--' }}</div>
          <el-tag size="small">{{ marketLabel(overview.market || market) }}</el-tag>
          <el-tag size="small" type="info" v-if="overview.fundamentals?.category" style="margin-left: 6px">
            {{ overview.fundamentals.category }}
          </el-tag>
        </div>
        <div class="hero-price" :class="changeClass(quote.changeRate)">
          <div class="price">{{ fmt(quote.last) }}</div>
          <div class="chg">
            {{ fmt(quote.change) }} / {{ fmtPct(quote.changeRate) }}
            <el-tag size="small" effect="plain" style="margin-left: 8px">{{ quote.source || 'history' }}</el-tag>
            <el-tag v-if="quote.source === 'live' || quote.source === 'longbridge'" size="small" type="danger" effect="plain" style="margin-left: 6px">LIVE</el-tag>
          </div>
        </div>
      </div>
      <el-row :gutter="12" class="quote-grid">
        <el-col :span="4"><div class="q-item"><span>今开</span><b>{{ fmt(quote.open) }}</b></div></el-col>
        <el-col :span="4"><div class="q-item"><span>最高</span><b>{{ fmt(quote.high) }}</b></div></el-col>
        <el-col :span="4"><div class="q-item"><span>最低</span><b>{{ fmt(quote.low) }}</b></div></el-col>
        <el-col :span="4"><div class="q-item"><span>成交量</span><b>{{ fmtVol(quote.volume) }}</b></div></el-col>
        <el-col :span="4"><div class="q-item"><span>日期</span><b>{{ quote.tradeDate || '--' }}</b></div></el-col>
        <el-col :span="4"><div class="q-item"><span>来源</span><b>{{ quote.source || '--' }}</b></div></el-col>
      </el-row>
    </el-card>

    <!-- 技术快照 -->
    <el-card shadow="never" class="panel mb16">
      <template #header><span class="panel-title">技术快照</span></template>
      <el-row :gutter="12">
        <el-col :xs="12" :sm="8" :md="4" v-for="cell in techCells" :key="cell.label">
          <div class="tech-cell">
            <div class="tech-label">{{ cell.label }}</div>
            <div class="tech-value">{{ cell.value }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- K线 -->
    <el-card shadow="never" class="panel mb16" v-loading="allLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">K线走势</span>
          <span class="panel-sub">近 {{ historyItems.length }} 日 · 截止 {{ historyEnd }}</span>
        </div>
      </template>
      <div ref="chartRef" class="kline-chart"></div>
    </el-card>

    <!-- AI 研判 -->
    <el-card shadow="never" class="panel mb16">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">AI 研判</span>
          <el-button type="success" size="small" icon="MagicStick" :loading="aiLoading" @click="handleAi" v-hasPermi="['market:ai:analyze']">
            {{ latestAi ? '重新研判' : '立即研判' }}
          </el-button>
        </div>
      </template>
      <div v-if="latestAi">
        <el-space wrap>
          <el-tag :type="decisionTag(latestAi.finalDecision || latestAi.recommendation)" effect="dark">{{ latestAi.finalDecision || latestAi.recommendation || '--' }}</el-tag>
          <el-tag v-if="latestAi.stance || latestAi.trend" type="info" effect="plain">{{ latestAi.stance || latestAi.trend }}</el-tag>
          <span>置信度 {{ latestAi.finalConfidence ?? latestAi.confidence ?? '--' }}%</span>
          <span class="muted">{{ latestAi.analysisTime || '--' }}</span>
        </el-space>
        <div class="ai-summary">{{ latestAi.summary || latestAi.summaryText || '--' }}</div>
        <el-descriptions :column="1" border size="small" style="margin-top: 12px">
          <el-descriptions-item label="指标">{{ latestAi.indicatorReview || '--' }}</el-descriptions-item>
          <el-descriptions-item label="舆情">{{ latestAi.sentimentReview || '--' }}</el-descriptions-item>
          <el-descriptions-item label="操作">{{ latestAi.operationAdvice || latestAi.advice || '--' }}</el-descriptions-item>
          <el-descriptions-item label="风险">{{ latestAi.riskWarning || '--' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <el-empty v-else description="暂无研判记录，点击立即研判" :image-size="70" />
    </el-card>

    <!-- 市场联动 -->
    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">市场动态</span></template>
          <div v-if="marketInsight">
            <div class="link-title">{{ marketInsight.headline }}</div>
            <div class="link-body">{{ marketInsight.summary }}</div>
          </div>
          <el-empty v-else description="暂无市场动态" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header><span class="panel-title">市场扫描</span></template>
          <div v-if="marketScan">
            <div class="link-title">{{ marketScan.headline }}</div>
            <div class="link-body">{{ marketScan.summary }}</div>
          </div>
          <el-empty v-else description="暂无扫描摘要" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 公告/资讯/讨论 -->
    <el-card shadow="never" class="panel">
      <el-tabs v-model="contentTab" @tab-change="onContentTab">
        <el-tab-pane label="公告" name="announcement" />
        <el-tab-pane label="资讯" name="news" />
        <el-tab-pane label="讨论" name="topic" />
      </el-tabs>
      <div class="content-actions">
        <el-button size="small" icon="Refresh" :loading="contentLoading" @click="loadContent(true)" v-hasPermi="['market:symbol:content']">强制刷新</el-button>
      </div>
      <el-table v-loading="contentLoading" :data="contentList" style="width: 100%">
        <el-table-column label="标题" prop="title" min-width="220" show-overflow-tooltip />
        <el-table-column label="摘要" prop="summary" min-width="240" show-overflow-tooltip />
        <el-table-column label="来源" prop="sourceName" width="120" />
        <el-table-column label="绑定" width="90">
          <template #default="scope">{{ scope.row.bind === 'briefing' ? '简报' : scope.row.bind === 'sentiment' ? '舆情' : '标的' }}</template>
        </el-table-column>
        <el-table-column label="时间" prop="publishedAt" width="170" />
        <el-table-column label="操作" width="110" align="center">
          <template #default="scope">
            <el-button
              link
              type="primary"
              @click="openDrawer(scope.row)"
              :disabled="!scope.row.sourceLink && !(scope.row.content || scope.row.summary)"
            >查看内容</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!contentLoading && contentList.length === 0" description="暂无该标的资讯" :image-size="60" />
    </el-card>

    <el-drawer v-model="drawerOpen" size="50%" :title="drawerTitle || '内容详情'">
      <div v-if="drawerContent" class="drawer-body">{{ drawerContent }}</div>
      <el-empty v-else-if="!drawerUrl" description="暂无正文" :image-size="60" />
      <div v-if="drawerUrl" class="drawer-link">
        <el-link type="primary" :href="drawerUrl" target="_blank">打开原文链接</el-link>
      </div>
      <!-- 有正文时不强制 iframe（很多站点禁止嵌入）；仅无正文时尝试预览 -->
      <iframe v-if="drawerUrl && !drawerContent" :src="drawerUrl" class="iframe-box" />
    </el-drawer>
  </div>
</template>

<script setup name="MarketSymbolIndex">
import echarts from '@/utils/echarts'
import { listInstrument, getSymbolOverview, symbolAiAnalyze, getSymbolContent, getLatestAi, pollMarketJob } from '@/api/market'
import { getQuotesHub } from '@/composables/useMarketQuotesWs'

const { proxy } = getCurrentInstance()
const route = useRoute()
const router = useRouter()

const instruments = ref([])
const symbol = ref((route.query.symbol || route.params.symbol || 'AAPL') + '')
const market = ref((route.query.market || 'US') + '')
const symbolKey = ref(symbol.value + '|' + market.value)

const overview = ref({})
const quote = ref({})
const tech = ref({})
const latestAi = ref(null)
const marketInsight = ref(null)
const marketScan = ref(null)
const historyItems = ref([])
const coreLoading = ref(false)
const allLoading = ref(false)
const aiLoading = ref(false)
const contentTab = ref('news')
const contentList = ref([])
const contentLoading = ref(false)
const drawerOpen = ref(false)
const drawerUrl = ref('')
const drawerTitle = ref('')
const drawerContent = ref('')
const chartRef = ref(null)
let chart = null

const historyEnd = computed(() => {
  const items = historyItems.value
  return items.length ? items[items.length - 1].date : '--'
})

const techCells = computed(() => {
  const t = tech.value || {}
  return [
    { label: '趋势', value: t.trendLabel || '--' },
    { label: 'RSI', value: fmt(t.rsi) },
    { label: '动量', value: t.momentumScore ?? '--' },
    { label: '支撑', value: fmt(t.supportPrice) },
    { label: '阻力', value: fmt(t.resistancePrice) },
    { label: 'ATR', value: fmt(t.atr) }
  ]
})

function marketLabel(m) {
  return { US: '美股', CN: 'A股', HK: '港股' }[m] || m || '--'
}
function fmt(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : String(v)
}
function fmtPct(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) + '%' : String(v)
}
function fmtVol(v) {
  if (v === null || v === undefined) return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}
function changeClass(rate) {
  const n = Number(rate)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}
function decisionTag(d) {
  if (!d) return 'info'
  if (String(d).includes('买') || d === 'BUY') return 'danger'
  if (String(d).includes('卖') || d === 'SELL') return 'success'
  return 'warning'
}
function goBack() {
  router.back()
}
function openDrawer(row) {
  drawerTitle.value = row.title || '内容详情'
  drawerContent.value = row.content || row.summary || ''
  drawerUrl.value = row.sourceLink || ''
  drawerOpen.value = true
}

function loadInstruments() {
  listInstrument().then(res => {
    instruments.value = res.data || []
  })
}

function onSymbolChange(val) {
  const [s, m] = String(val).split('|')
  symbol.value = s
  market.value = m || 'US'
  contentList.value = []
  router.replace({ path: '/market/symbol', query: { symbol: s, market: m || 'US' } })
  loadAll()
}

let unsubQuotes = null
function quoteMatches(q, sym, mkt) {
  return String(q.symbol || '').toUpperCase() === String(sym || '').toUpperCase()
    && String(q.market || 'US').toUpperCase() === String(mkt || 'US').toUpperCase()
}
function dropQuoteSub() {
  if (unsubQuotes) { unsubQuotes(); unsubQuotes = null }
}
function syncQuoteSub() {
  dropQuoteSub()
  if (!symbol.value) return
  unsubQuotes = getQuotesHub().subscribeQuotes([{ symbol: symbol.value, market: market.value || 'US' }], (payload) => {
    const hit = ((payload && payload.items) || []).find(q => quoteMatches(q, symbol.value, market.value))
    if (!hit || hit.last == null) return
    const last = Number(hit.last)
    const prev = Number(quote.value.prevClose || quote.value.preClose)
    const chg = hit.changePct ?? hit.changeRate
    quote.value = {
      ...quote.value,
      last,
      changeRate: chg != null ? Number(chg) : (prev ? (last / prev - 1) * 100 : quote.value.changeRate),
      change: prev ? last - prev : quote.value.change,
      source: hit.source || 'live',
      quoteTime: hit.quoteTime || quote.value.quoteTime
    }
  })
}

function applyCore(data) {
  overview.value = data || {}
  quote.value = data.quote || {}
  tech.value = data.techSnapshot || {}
  latestAi.value = data.latestAiAnalysis || null
  syncQuoteSub()
}

function applyAll(data) {
  historyItems.value = (data.history && data.history.items) || []
  marketInsight.value = data.marketInsight || null
  marketScan.value = data.marketScan || null
  const cache = data.contentCache || {}
  if (cache[contentTab.value]) {
    contentList.value = cache[contentTab.value]
  } else {
    // overview 未内嵌当前 Tab 内容时主动拉取，否则首屏内容 Tab 一直空白
    loadContent(false)
  }
  renderChart()
}

function loadAll() {
  coreLoading.value = true
  getSymbolOverview(symbol.value, { market: market.value, include: 'core' })
    .then(res => {
      applyCore(res.data || {})
      allLoading.value = true
      return getSymbolOverview(symbol.value, { market: market.value, include: 'all', historyLimit: 120 })
    })
    .then(res => {
      if (res && res.data) applyAll(res.data)
    })
    .finally(() => {
      coreLoading.value = false
      allLoading.value = false
    })
}

function applyLatestAi(data) {
  latestAi.value = {
    finalDecision: data.finalDecision || data.recommendation,
    recommendation: data.recommendation || data.finalDecision,
    finalConfidence: data.finalConfidence ?? data.confidence,
    confidence: data.confidence ?? data.finalConfidence,
    stance: data.stance || data.trend,
    trend: data.trend || data.stance,
    summary: data.summary || data.summaryText,
    indicatorReview: data.indicatorReview,
    sentimentReview: data.sentimentReview,
    operationAdvice: data.operationAdvice || data.advice,
    advice: data.advice || data.operationAdvice,
    riskWarning: data.riskWarning,
    analysisTime: data.analysisTime || new Date().toLocaleString()
  }
}

async function handleAi() {
  aiLoading.value = true
  try {
    const res = await symbolAiAnalyze(symbol.value, { market: market.value, days: 120 })
    const data = res.data || {}
    if (data.accepted || data.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队')
      if (data.jobId) {
        const ticket = await pollMarketJob(data.jobId)
        if (ticket.status === 'failed') {
          proxy.$modal.msgError(ticket.error || '研判失败')
          return
        }
      }
      const latest = await getLatestAi(symbol.value, { market: market.value })
      applyLatestAi(latest.data || {})
      return
    }
    if (data.ok) {
      proxy.$modal.msgSuccess(data.message || '研判完成')
      applyLatestAi(data)
    } else {
      proxy.$modal.msgWarning(data.message || '研判失败')
    }
  } finally {
    aiLoading.value = false
  }
}

function loadContent(refresh = false) {
  contentLoading.value = true
  getSymbolContent(symbol.value, {
    market: market.value,
    type: contentTab.value,
    limit: 20,
    refresh: !!refresh,
    related: contentTab.value === 'news'
  })
    .then(res => {
      contentList.value = (res.data && res.data.items) || []
    })
    .finally(() => {
      contentLoading.value = false
    })
}

function onContentTab() {
  loadContent(false)
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const items = historyItems.value || []
  chart.setOption({
    grid: { left: 48, right: 16, top: 24, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: items.map(i => i.date), boundaryGap: false },
    yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        type: 'line',
        data: items.map(i => i.close),
        smooth: true,
        showSymbol: false,
        areaStyle: { opacity: 0.12 },
        lineStyle: { width: 2 }
      }
    ]
  })
}

function handleResize() {
  chart && chart.resize()
}

onMounted(() => {
  loadInstruments()
  loadAll()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  dropQuoteSub()
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style lang="scss" scoped>
.symbol-detail {
  .top-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 12px;
  }
  .panel {
    border-radius: 12px;
  }
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .panel-title {
    font-weight: 600;
  }
  .panel-sub {
    font-size: 12px;
    color: #909399;
  }
  .hero {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
    .hero-code {
      font-size: 24px;
      font-weight: 700;
    }
    .hero-name {
      color: #606266;
      margin: 4px 0 8px;
    }
    .hero-price {
      text-align: right;
      .price {
        font-size: 32px;
        font-weight: 700;
      }
      &.up .price,
      &.up .chg {
        color: #f56c6c;
      }
      &.down .price,
      &.down .chg {
        color: #67c23a;
      }
    }
  }
  .quote-grid .q-item {
    background: var(--el-fill-color-light);
    border-radius: 8px;
    padding: 10px;
    span {
      display: block;
      font-size: 12px;
      color: #909399;
      margin-bottom: 4px;
    }
    b {
      font-size: 14px;
    }
  }
  .tech-cell {
    background: var(--el-fill-color-light);
    border-radius: 10px;
    padding: 14px 12px;
    margin-bottom: 10px;
    text-align: center;
    .tech-label {
      font-size: 12px;
      color: #909399;
      margin-bottom: 6px;
    }
    .tech-value {
      font-size: 16px;
      font-weight: 600;
    }
  }
  .kline-chart {
    height: 360px;
  }
  .ai-summary {
    margin-top: 12px;
    line-height: 1.7;
    color: var(--text-emphasis, #303133);
  }
  .muted {
    color: #909399;
    font-size: 12px;
  }
  .link-title {
    font-weight: 600;
    margin-bottom: 8px;
  }
  .link-body {
    color: #606266;
    line-height: 1.6;
    font-size: 13px;
  }
  .content-actions {
    margin-bottom: 8px;
  }
  .iframe-box {
    width: 100%;
    height: 80vh;
    border: 0;
  }
  .drawer-body {
    white-space: pre-wrap;
    line-height: 1.75;
    font-size: 14px;
    color: var(--text-emphasis, #303133);
    margin-bottom: 16px;
  }
  .drawer-link {
    margin-bottom: 12px;
  }
  .mb16 {
    margin-bottom: 16px;
  }
}
</style>
