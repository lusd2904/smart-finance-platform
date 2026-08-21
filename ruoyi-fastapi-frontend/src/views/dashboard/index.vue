<template>
  <div class="home-page">
    <!-- 欢迎区 -->
    <div class="hero-card">
      <div class="hero-left">
        <div class="hero-greet">{{ greetText }}，{{ displayName }}</div>
        <div class="hero-sub">
          智慧金融分析平台 · 舆情 AI · 真实行情时序 · 量化策略
        </div>
        <div class="hero-time">{{ nowText }}</div>
      </div>
      <div class="hero-actions">
        <el-button type="primary" icon="Refresh" :loading="loading" @click="refreshAll">刷新数据</el-button>
        <el-button icon="Grid" @click="go('/portal')">子系统门户</el-button>
        <el-button icon="DataLine" @click="go('/sentiment/dashboard')">舆情大盘</el-button>
        <el-button icon="TrendCharts" @click="go('/market/kline')">行情 K 线</el-button>
      </div>
    </div>

    <!-- 核心指标 -->
    <el-row :gutter="16" class="mb16">
      <el-col :xs="12" :sm="6" v-for="item in statCards" :key="item.key">
        <div class="stat-card" :class="item.tone" @click="item.path && go(item.path)">
          <div class="stat-icon">
            <el-icon><component :is="item.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-label">{{ item.label }}</div>
            <div class="stat-value">{{ item.value }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card mb16" v-loading="reviewLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">市场分析</span>
          <span class="panel-sub">美股 · 港股 · A股 收盘复盘</span>
          <el-button link type="primary" @click="go('/market/review')">历史记录</el-button>
        </div>
      </template>
      <el-row :gutter="12" v-if="marketReviews.length">
        <el-col :xs="24" :md="8" v-for="item in marketReviews" :key="item.market">
          <div class="review-card" :class="reviewTone(item.stance)" @click="go('/market/review')">
            <div class="review-head">
              <strong>{{ item.marketLabel }}</strong>
              <el-tag size="small" :type="reviewTag(item.stance)" effect="dark">{{ item.stance || '待分析' }}</el-tag>
            </div>
            <div class="review-meta">{{ item.tradeDate || '--' }} · 温度 {{ item.score != null ? item.score : '--' }}</div>
            <p class="review-summary">{{ item.summary || '暂无当日复盘' }}</p>
          </div>
        </el-col>
      </el-row>
      <el-empty v-else description="暂无收盘复盘，可到行情中心「市场分析」立即生成" :image-size="72">
        <el-button type="primary" @click="go('/market/review')">去市场分析</el-button>
      </el-empty>
    </el-card>

    <!-- 快捷导航 -->
    <el-card shadow="never" class="panel-card mb16">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">快捷导航</span>
          <span class="panel-sub">业务入口一键直达</span>
        </div>
      </template>
      <el-row :gutter="12">
        <el-col :xs="12" :sm="8" :md="6" v-for="nav in navItems" :key="nav.path">
          <div class="nav-item" @click="go(nav.path)">
            <div class="nav-icon" :style="{ background: nav.bg }">
              <el-icon :size="22"><component :is="nav.icon" /></el-icon>
            </div>
            <div class="nav-text">
              <div class="nav-title">{{ nav.title }}</div>
              <div class="nav-desc">{{ nav.desc }}</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16">
      <!-- 最新舆情分析 -->
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="panel-card mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">最新舆情研判</span>
              <el-button link type="primary" @click="go('/sentiment/analysis')">查看全部</el-button>
            </div>
          </template>
          <template v-if="latestAnalysis.summary">
            <div class="analysis-meta">
              <el-tag size="small" effect="plain">{{ latestAnalysis.modelName || 'AI' }}</el-tag>
              <span class="meta-time">{{ latestAnalysis.createTime || '--' }}</span>
            </div>
            <div class="analysis-summary">{{ latestAnalysis.summary }}</div>
            <el-row :gutter="12" class="score-row">
              <el-col :span="8" v-for="m in marketScores" :key="m.key">
                <div class="score-box" :class="m.cls">
                  <div class="score-name">{{ m.name }}</div>
                  <div class="score-val">{{ m.score }}</div>
                  <div class="score-dir">{{ m.direction || '暂无' }}</div>
                </div>
              </el-col>
            </el-row>
            <div class="risk-block" v-if="latestAnalysis.riskEvents">
              <div class="risk-title">风险提示</div>
              <div class="risk-text">{{ latestAnalysis.riskEvents }}</div>
            </div>
          </template>
          <el-empty v-else description="暂无舆情分析，可先采集资讯再执行分析" :image-size="90">
            <el-button type="primary" @click="go('/sentiment/dashboard')">去舆情大盘</el-button>
          </el-empty>
        </el-card>

        <!-- 动态：最近分析 / 资讯 -->
        <el-card shadow="never" class="panel-card mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">平台动态</span>
              <span class="panel-sub">最近分析与资讯</span>
            </div>
          </template>
          <el-timeline v-if="activities.length">
            <el-timeline-item
              v-for="(act, idx) in activities"
              :key="idx"
              :timestamp="act.time"
              placement="top"
              :type="act.type"
            >
              <div class="act-title">{{ act.title }}</div>
              <div class="act-desc">{{ act.desc }}</div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无动态" :image-size="80" />
        </el-card>
      </el-col>

      <!-- 行情快照 + 模块说明 -->
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="panel-card mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">行情快照</span>
              <el-button link type="primary" @click="go('/market/kline')">K 线中心</el-button>
            </div>
          </template>
          <div v-if="quotes.length" class="quote-list">
            <div class="quote-row" v-for="q in quotes" :key="q.symbol" @click="goKline(q.symbol)">
              <div class="q-left">
                <span class="q-symbol">{{ q.symbol }}</span>
                <span class="q-name">{{ q.name }}</span>
              </div>
              <div class="q-right" :class="q.up ? 'up' : 'down'">
                <span class="q-price">{{ q.price }}</span>
                <span class="q-chg">{{ q.changeText }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无行情，请先同步至时序库" :image-size="80">
            <el-button type="primary" @click="go('/market/dashboard')">去行情中心</el-button>
          </el-empty>
        </el-card>

        <el-card shadow="never" class="panel-card mb16">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">模块能力</span>
            </div>
          </template>
          <div class="module-list">
            <div class="module-item" v-for="m in modules" :key="m.title">
              <div class="module-dot" :style="{ background: m.color }"></div>
              <div>
                <div class="module-title">{{ m.title }}</div>
                <div class="module-desc">{{ m.desc }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="Index">
import useUserStore from '@/store/modules/user'
import { getStats, listAnalysis, listNews } from '@/api/sentiment'
import { listInstrument, getKline, getMarketReviewLatest } from '@/api/market'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const nowText = ref('')
const stats = ref({ total: 0, today: 0, unanalyzed: 0 })
const latestAnalysis = ref({})
const activities = ref([])
const quotes = ref([])
const instrumentCount = ref(0)
const marketReviews = ref([])
const reviewLoading = ref(false)

const displayName = computed(() => userStore.nickName || userStore.name || '管理员')

const greetText = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const statCards = computed(() => [
  { key: 'total', label: '舆情资讯', value: stats.value.total ?? 0, icon: 'Document', tone: 'tone-blue', path: '/sentiment/news' },
  { key: 'today', label: '今日新增', value: stats.value.today ?? 0, icon: 'Calendar', tone: 'tone-green', path: '/sentiment/news' },
  { key: 'wait', label: '待分析', value: stats.value.unanalyzed ?? 0, icon: 'Clock', tone: 'tone-orange', path: '/sentiment/dashboard' },
  { key: 'inst', label: '行情标的', value: instrumentCount.value ?? 0, icon: 'Coin', tone: 'tone-purple', path: '/market/symbol' }
])

const navItems = [
  { title: '舆情大盘', desc: 'AI 影响分与趋势', path: '/sentiment/dashboard', icon: 'DataAnalysis', bg: 'linear-gradient(135deg,#6366f1,#8b5cf6)' },
  { title: '资讯列表', desc: '正文站内查看', path: '/sentiment/news', icon: 'Reading', bg: 'linear-gradient(135deg,#0ea5e9,#38bdf8)' },
  { title: '分析结果', desc: '历史研判记录', path: '/sentiment/analysis', icon: 'Tickets', bg: 'linear-gradient(135deg,#10b981,#34d399)' },
  { title: '行情中心', desc: '标的与同步', path: '/market/dashboard', icon: 'TrendCharts', bg: 'linear-gradient(135deg,#f59e0b,#fbbf24)' },
  { title: 'K 线指标', desc: '真实行情时序', path: '/market/kline', icon: 'DataLine', bg: 'linear-gradient(135deg,#ef4444,#f87171)' },
  { title: '财经简报', desc: '市场资讯聚合', path: '/market/finance-news', icon: 'Notebook', bg: 'linear-gradient(135deg,#14b8a6,#2dd4bf)' },
  { title: '量化策略', desc: '策略与扫描', path: '/quant/strategy', icon: 'Cpu', bg: 'linear-gradient(135deg,#8b5cf6,#a78bfa)' },
  { title: '自选池', desc: '关注标的管理', path: '/quant/watchlist', icon: 'Star', bg: 'linear-gradient(135deg,#ec4899,#f472b6)' },
  { title: '行情自选', desc: '小时级综合建议', path: '/market/watchlist', icon: 'Aim', bg: 'linear-gradient(135deg,#f97316,#fb923c)' },
  { title: '市场分析', desc: '美股/港股/A股收盘复盘', path: '/market/review', icon: 'Notebook', bg: 'linear-gradient(135deg,#0ea5e9,#38bdf8)' }
]

const modules = [
  { title: '舆情分析', desc: '免费中文源采集 + AI 对美/港/A 股影响研判', color: '#6366f1' },
  { title: '行情数据', desc: '新浪真源日 K 直写 Influx，无 MySQL 中间层', color: '#0ea5e9' },
  { title: '量化模块', desc: '策略、因子、扫描结果与长桥接口', color: '#f59e0b' },
  { title: 'AI 管理', desc: '统一模型配置，舆情/行情共用连接参数', color: '#10b981' }
]

const marketScores = computed(() => {
  const a = latestAnalysis.value || {}
  const pack = (key, name, direction, score) => {
    const dir = direction || ''
    let cls = 'neutral'
    if (dir.includes('多')) cls = 'bull'
    else if (dir.includes('空')) cls = 'bear'
    return {
      key,
      name,
      direction: dir || '--',
      score: score === 0 || score ? score : '--',
      cls
    }
  }
  return [
    pack('us', '美股', a.usDirection, a.usScore),
    pack('hk', '港股', a.hkDirection, a.hkScore),
    pack('a', 'A股', a.aDirection, a.aScore)
  ]
})

const QUOTE_SYMBOLS = [
  { symbol: 'AAPL', name: '苹果' },
  { symbol: 'NVDA', name: '英伟达' },
  { symbol: 'MSFT', name: '微软' },
  { symbol: 'TSLA', name: '特斯拉' },
  { symbol: '^IXIC', name: '纳指' },
  { symbol: '^GSPC', name: '标普' }
]

function go(path) {
  if (!path) return
  router.push(path).catch(() => {})
}

function reviewTag(stance) {
  if (stance === '偏多') return 'danger'
  if (stance === '偏空') return 'success'
  return 'info'
}
function reviewTone(stance) {
  if (stance === '偏多') return 'bull'
  if (stance === '偏空') return 'bear'
  return 'neutral'
}
function goKline(symbol) {
  router.push({ path: '/market/kline', query: { symbol } }).catch(() => {})
}

function tickClock() {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  nowText.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function loadSentiment() {
  try {
    const res = await getStats()
    const data = res.data || {}
    stats.value = {
      total: data.total ?? 0,
      today: data.today ?? 0,
      unanalyzed: data.unanalyzed ?? 0
    }
    latestAnalysis.value = data.latestAnalysis || {}
  } catch (e) {
    /* ignore */
  }

  try {
    const [analysisRes, newsRes] = await Promise.all([
      listAnalysis({ pageNum: 1, pageSize: 5 }),
      listNews({ pageNum: 1, pageSize: 5 })
    ])
    const acts = []
    for (const row of analysisRes.rows || []) {
      acts.push({
        time: row.createTime || '',
        type: String(row.status) === '0' ? 'success' : 'danger',
        title: String(row.status) === '0' ? '舆情 AI 分析完成' : '舆情 AI 分析失败',
        desc: (row.summary || row.errorMsg || `共分析 ${row.newsCount || 0} 条资讯`).slice(0, 120)
      })
    }
    for (const row of newsRes.rows || []) {
      acts.push({
        time: row.pubTime || row.createTime || '',
        type: 'primary',
        title: `[${row.source || '资讯'}] ${row.title || ''}`.slice(0, 60),
        desc: (row.content || row.title || '').slice(0, 100)
      })
    }
    acts.sort((a, b) => String(b.time).localeCompare(String(a.time)))
    activities.value = acts.slice(0, 8)
  } catch (e) {
    /* ignore */
  }
}

async function loadMarketReviews() {
  reviewLoading.value = true
  try {
    const res = await getMarketReviewLatest()
    marketReviews.value = (res.data && res.data.items) || []
  } catch (e) {
    marketReviews.value = []
  } finally {
    reviewLoading.value = false
  }
}

async function loadMarket() {
  try {
    const res = await listInstrument()
    const list = res.data || res.rows || []
    instrumentCount.value = Array.isArray(list) ? list.length : 0
  } catch (e) {
    instrumentCount.value = 0
  }

  const nextQuotes = []
  for (const item of QUOTE_SYMBOLS) {
    try {
      const res = await getKline({ symbol: item.symbol, market: 'US', start: '-10d', stop: 'now()' })
      const klines = (res.data && res.data.klines) || res.data || []
      if (!Array.isArray(klines) || klines.length === 0) continue
      const last = klines[klines.length - 1]
      const prev = klines.length > 1 ? klines[klines.length - 2] : null
      const price = Number(last.close)
      let change = 0
      if (prev && prev.close) change = ((price - Number(prev.close)) / Number(prev.close)) * 100
      const up = change >= 0
      nextQuotes.push({
        symbol: item.symbol,
        name: item.name,
        price: Number.isFinite(price) ? price.toFixed(2) : '--',
        changeText: Number.isFinite(change) ? `${up ? '+' : ''}${change.toFixed(2)}%` : '--',
        up
      })
    } catch (e) {
      /* skip symbol */
    }
  }
  quotes.value = nextQuotes
}

async function refreshAll() {
  loading.value = true
  tickClock()
  try {
    await Promise.all([loadSentiment(), loadMarket(), loadMarketReviews()])
  } finally {
    loading.value = false
  }
}

let clockTimer = null
onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  refreshAll()
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped lang="scss">
.home-page {
  padding: 16px;
  min-height: calc(100vh - 120px);
  background: linear-gradient(180deg, var(--page-bg) 0%, var(--surface-soft) 220px, var(--page-bg) 100%);
  color: var(--text-emphasis);
}

.mb16 {
  margin-bottom: 16px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 22px 24px;
  margin-bottom: 16px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%);
  box-shadow: 0 12px 30px rgba(79, 70, 229, 0.25);
}

.hero-greet {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 6px;
}

.hero-sub {
  opacity: 0.92;
  font-size: 14px;
}

.hero-time {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.8;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  margin-bottom: 12px;
  border-radius: 14px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-glow);
  }
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
}

.tone-blue .stat-icon { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
.tone-green .stat-icon { background: linear-gradient(135deg, #10b981, #34d399); }
.tone-orange .stat-icon { background: linear-gradient(135deg, #f59e0b, #fbbf24); }
.tone-purple .stat-icon { background: linear-gradient(135deg, #8b5cf6, #a78bfa); }

.stat-label {
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
  line-height: 1.2;
}

.panel-card {
  border-radius: 14px;
  border: 1px solid var(--border-soft, #eef2ff);
  :deep(.el-card__header) {
    border-bottom: 1px solid #f1f5f9;
    padding: 14px 18px;
  }
  :deep(.el-card__body) {
    padding: 16px 18px;
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
}

.panel-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
  margin-right: 8px;
}

.review-card {
  border-radius: 12px;
  padding: 14px;
  min-height: 168px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  margin-bottom: 8px;
  &.bull { border-color: #fecaca; }
  &.bear { border-color: #bbf7d0; }
}
.review-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.review-meta { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.review-summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 12px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  transition: all 0.2s ease;
  &:hover {
    background: var(--surface-hover, #eef2ff);
    transform: translateY(-1px);
  }
}

.nav-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-title {
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
  font-size: 14px;
}

.nav-desc {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.analysis-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.meta-time {
  color: #94a3b8;
  font-size: 12px;
}

.analysis-summary {
  line-height: 1.7;
  color: #334155;
  margin-bottom: 14px;
  white-space: pre-wrap;
}

.score-row {
  margin-bottom: 8px;
}

.score-box {
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #e2e8f0);
  margin-bottom: 8px;
  &.bull {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.35);
    .score-val { color: var(--stat-down, #059669); }
  }
  &.bear {
    background: rgba(239, 68, 68, 0.12);
    border-color: rgba(239, 68, 68, 0.35);
    .score-val { color: var(--stat-up, #dc2626); }
  }
  &.neutral {
    .score-val { color: var(--text-secondary, #475569); }
  }
}

.score-name {
  font-size: 12px;
  color: #64748b;
}

.score-val {
  font-size: 22px;
  font-weight: 700;
  margin: 4px 0;
}

.score-dir {
  font-size: 12px;
  color: #64748b;
}

.risk-block {
  margin-top: 8px;
  padding: 12px;
  border-radius: 10px;
  background: var(--risk-bg, #fff7ed);
  border: 1px solid var(--risk-border, #fed7aa);
}

.risk-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--risk-title, #c2410c);
  margin-bottom: 4px;
}

.risk-text {
  font-size: 13px;
  color: var(--risk-text, #9a3412);
  line-height: 1.6;
}

.act-title {
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
  margin-bottom: 2px;
}

.act-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

.quote-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quote-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  transition: background 0.15s ease;
  &:hover { background: var(--surface-hover, #eef2ff); }
}

.q-symbol {
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
  margin-right: 8px;
}

.q-name {
  font-size: 12px;
  color: #94a3b8;
}

.q-right {
  text-align: right;
  &.up { color: #dc2626; }
  &.down { color: #059669; }
}

.q-price {
  display: block;
  font-weight: 700;
  font-size: 15px;
}

.q-chg {
  font-size: 12px;
}

.module-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.module-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.module-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.module-title {
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
  margin-bottom: 2px;
}

.module-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .hero-greet { font-size: 20px; }
  .home-page { padding: 12px; }
}
</style>
