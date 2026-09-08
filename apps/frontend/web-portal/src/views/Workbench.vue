<template>
  <div class="dashboard-page workbench-page" v-loading="loading">
    <div v-if="usingStub && !hideStubBanner()" class="stub-banner">演示</div>

    <section class="hero-panel workbench-hero">
      <div class="hero-copy">
        <h2>{{ greetText }}，{{ userStore.displayName }}</h2>
      </div>
      <div class="header-actions">
        <span
          v-for="s in sessions"
          :key="s.market"
          class="session-chip"
          :class="`status-${s.status}`"
        >
          <i class="dot"></i>{{ s.label }} {{ sessionText(s) }}
        </span>
        <el-button type="primary" :loading="loading" @click="refreshAll(true)">刷新</el-button>
      </div>
    </section>

    <div v-if="assetVisible" class="asset-strip">
      <article v-for="card in assetCards" :key="card.key" class="stat-card glass-panel" @click="$router.push(card.path)">
        <span>{{ card.label }}</span>
        <strong :class="card.cls">{{ card.value }}</strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>市场分析</h3>
          <el-button link type="primary" @click="$router.push('/market/review')">历史记录</el-button>
        </div>
      </template>
      <div v-if="marketReviews.length" class="review-grid">
        <article v-for="item in marketReviews" :key="item.market" class="review-card" :class="reviewTone(item.stance)" @click="$router.push('/market/review')">
          <div class="review-head">
            <strong>{{ item.marketLabel }}</strong>
            <el-tag size="small" :type="reviewTag(item.stance)">{{ item.stance || '待分析' }}</el-tag>
          </div>
          <div class="muted">{{ item.tradeDate || '--' }} · 温度 {{ item.score ?? '--' }}</div>
          <p>{{ item.summary || '暂无当日复盘' }}</p>
        </article>
      </div>
      <el-empty v-else description="暂无收盘复盘" :image-size="64">
        <el-button type="primary" @click="$router.push('/market/review')">去市场分析</el-button>
      </el-empty>
    </el-card>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>快捷入口</h3>
        </div>
      </template>
      <div class="quick-nav">
        <button v-for="nav in navItems" :key="nav.path" type="button" class="nav-item" @click="$router.push(nav.path)">
          <el-icon><component :is="nav.icon" /></el-icon>
          <span>{{ nav.title }}</span>
        </button>
      </div>
    </el-card>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>最新舆情研判</h3></div></template>
          <template v-if="latest.summary">
            <p>{{ latest.summary }}</p>
            <div class="score-row">
              <div v-for="m in marketScores" :key="m.key" class="score-box" :class="m.cls">
                <span>{{ m.name }}</span>
                <strong>{{ m.score }}</strong>
                <small>{{ m.direction }}</small>
              </div>
            </div>
          </template>
          <el-empty v-else description="暂无舆情分析" :image-size="64" />
        </el-card>
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>财经简报</h3></div></template>
          <div v-if="briefings.length" class="brief-list">
            <div v-for="item in briefings" :key="item.id" class="brief-item">
              <strong>{{ item.title }}</strong>
              <span>{{ item.source }} · {{ item.time }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无简报" :image-size="64" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>三市场热度</h3></div></template>
          <div class="heat-grid">
            <div v-for="m in heatRows" :key="m.market" class="heat-box">
              <div class="heat-head"><strong>{{ m.label }}</strong><span>{{ m.data?.tradeDate }}</span></div>
              <div class="heat-index">
                <span>{{ m.data?.indexName || '--' }}</span>
                <b :class="changeClass(m.data?.indexChangePct)">{{ fmtChange(m.data?.indexChangePct) }}</b>
              </div>
              <div class="muted">涨 {{ m.data?.advanceCount ?? '-' }} / 跌 {{ m.data?.declineCount ?? '-' }}</div>
            </div>
          </div>
        </el-card>
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>自选信号</h3></div></template>
          <div v-for="item in watchItems" :key="item.symbol" class="quote-row" @click="$router.push('/trade/terminal')">
            <div><strong>{{ item.symbol }}</strong><span class="muted"> {{ item.name }}</span></div>
            <b :class="changeClass(item.changeRate)">{{ fmtChange(item.changeRate) }}</b>
          </div>
          <el-empty v-if="!watchItems.length" description="暂无自选信号" :image-size="56" />
        </el-card>
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>行情快照</h3></div></template>
          <div v-for="q in quoteRows" :key="q.symbol" class="quote-row">
            <div><strong>{{ q.symbol }}</strong><span class="muted"> {{ q.name }}</span></div>
            <div class="q-right" :class="changeClass(q.changeRate)">
              <span>{{ q.price ?? '--' }}</span>
              <b>{{ fmtChange(q.changeRate) }}</b>
            </div>
          </div>
          <el-empty v-if="!quoteRows.length" description="暂无行情" :image-size="56" />
        </el-card>
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>平台运行状态</h3></div></template>
          <div class="health-grid">
            <div>
              <span class="muted">K线覆盖率</span>
              <strong>{{ health.coverage?.coveragePct ?? '--' }}%</strong>
            </div>
            <div>
              <span class="muted">24h 任务</span>
              <strong>{{ health.jobs ? `${health.jobs.success || 0} 成功` : '--' }}</strong>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getDashboardSummary } from '@/api/dashboard'
import { getMarketReviewLatest } from '@/api/market'
import { useUserStore } from '@/store/user'
import { changeClass, fmtAmount, fmtChange, sectionOk } from '@/utils/format'
import { hideStubBanner, stubDashboard, stubReviews, useStubs } from '@/utils/stubs'

const userStore = useUserStore()
const loading = ref(false)
const usingStub = ref(false)
const summary = ref({})
const marketReviews = ref([])

const greetText = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const sessions = computed(() =>
  [
    { market: 'US', label: '美股' },
    { market: 'HK', label: '港股' },
    { market: 'CN', label: 'A股' }
  ].map((m) => {
    const found = (summary.value.sessions || []).find((s) => s.market === m.market)
    return found ? { ...m, ...found } : { ...m, status: 'unknown' }
  })
)

function sessionText(s) {
  if (s.status === 'open') return '开市'
  if (s.status === 'weekend') return '休市'
  if (s.status === 'closed') return '已收盘'
  return '--'
}

const asset = computed(() => (summary.value.asset && summary.value.asset.data) || {})
const assetVisible = computed(() => Boolean(summary.value.asset && summary.value.asset.reason !== 'denied' && asset.value.configured))
const assetCards = computed(() => [
  { key: 'net', label: `总净值(${asset.value.currency || '--'})`, value: fmtAmount(asset.value.netAssets), cls: '', path: '/trade/terminal' },
  { key: 'cash', label: '可用资金', value: fmtAmount(asset.value.availableCash), cls: '', path: '/trade/terminal' },
  { key: 'pos', label: '持仓数', value: String(asset.value.positionCount ?? 0), cls: '', path: '/trade/terminal' },
  { key: 'pnl', label: '浮动盈亏', value: fmtAmount(asset.value.totalUnrealizedPnl), cls: changeClass(asset.value.totalUnrealizedPnl), path: '/trade/terminal' }
])

const latest = computed(() => ((summary.value.sentiment && summary.value.sentiment.data) || {}).latestAnalysis || {})
const marketScores = computed(() => {
  const a = latest.value || {}
  const pack = (key, name, direction, score) => {
    const dir = direction || ''
    let cls = 'neutral'
    if (dir.includes('多')) cls = 'bull'
    else if (dir.includes('空')) cls = 'bear'
    return { key, name, direction: dir || '--', score: score === 0 || score ? score : '--', cls }
  }
  return [pack('us', '美股', a.usDirection, a.usScore), pack('hk', '港股', a.hkDirection, a.hkScore), pack('a', 'A股', a.aDirection, a.aScore)]
})

const briefings = computed(() => ((summary.value.briefings && summary.value.briefings.data) || {}).items || [])
const heatRows = computed(() => {
  const data = (summary.value.heat && summary.value.heat.data) || {}
  return [
    { market: 'US', label: '美股', data: data.US },
    { market: 'HK', label: '港股', data: data.HK },
    { market: 'CN', label: 'A股', data: data.CN }
  ]
})
const watchItems = computed(() => ((summary.value.watchSignals && summary.value.watchSignals.data) || {}).items || [])
const quoteRows = computed(() => {
  const d = (summary.value.quotes && summary.value.quotes.data) || {}
  return [...(d.indices || []), ...(d.quotes || [])]
})
const health = computed(() => (summary.value.health && summary.value.health.data) || {})

const navItems = [
  { title: '交易终端', path: '/trade/terminal', icon: 'Monitor' },
  { title: '舆情大盘', path: '/sentiment/dashboard', icon: 'DataAnalysis' },
  { title: '资讯列表', path: '/sentiment/news', icon: 'Reading' },
  { title: '行情中心', path: '/market/heat', icon: 'TrendCharts' },
  { title: '资金与日历', path: '/market/flow', icon: 'Money' },
  { title: '行情台', path: '/market/board', icon: 'DataLine' },
  { title: '财经简报', path: '/market/finance-news', icon: 'Notebook' },
  { title: '量化策略', path: '/quant/strategy', icon: 'Cpu' },
  { title: '自选清单', path: '/market/watchlist', icon: 'Star' },
  { title: '市场分析', path: '/market/review', icon: 'Notebook' },
  { title: '自动分析', path: '/analysis/jobs', icon: 'Clock' }
]

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

function applyStub() {
  usingStub.value = true
  summary.value = stubDashboard()
  marketReviews.value = stubReviews()
}

async function refreshAll(force = false) {
  if (useStubs() || userStore.usingStub) {
    applyStub()
    return
  }
  loading.value = true
  try {
    const res = await getDashboardSummary(force ? { refresh: true } : {})
    const data = res.data || res
    if (!data || (!data.sessions && !data.asset && !sectionOk(data.quotes))) {
      applyStub()
    } else {
      usingStub.value = false
      summary.value = data
    }
    try {
      const reviewRes = await getMarketReviewLatest()
      marketReviews.value = (reviewRes.data && reviewRes.data.items) || reviewRes.items || []
      if (!marketReviews.value.length && usingStub.value) marketReviews.value = stubReviews()
    } catch {
      if (usingStub.value) marketReviews.value = stubReviews()
    }
  } catch {
    applyStub()
  } finally {
    loading.value = false
  }
}

onMounted(() => refreshAll())
</script>

<style scoped lang="scss">
.workbench-page {
  display: grid;
  gap: 10px;
}

.workbench-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; font-size: 15px; color: var(--text-emphasis); }
}

.session-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: color-mix(in srgb, var(--surface-soft) 80%, transparent);
  color: var(--text-emphasis);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-muted);
  }
  &.status-open .dot { background: var(--success); }
}

.asset-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.stat-card {
  padding: 12px 14px;
  display: grid;
  gap: 6px;
  cursor: pointer;
  span { color: var(--text-secondary); font-size: 12px; }
  strong { font-size: 18px; color: var(--text-emphasis); font-variant-numeric: tabular-nums; }
}

.review-grid,
.score-row,
.heat-grid,
.health-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.review-card,
.score-box,
.heat-box {
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-soft);
  display: grid;
  gap: 6px;
}

.review-head,
.heat-head,
.quote-row,
.brief-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.quick-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: color-mix(in srgb, var(--surface-soft) 88%, transparent);
  color: var(--text-emphasis);
  cursor: pointer;
  .el-icon { color: var(--accent); }
  &:hover {
    border-color: color-mix(in srgb, var(--accent) 32%, var(--border-soft));
    background: color-mix(in srgb, var(--accent) 10%, var(--surface-soft));
  }
}

.heat-index b,
.score-box strong,
.quote-row b,
.q-right,
.health-grid strong {
  font-variant-numeric: tabular-nums;
}

.muted { color: var(--text-secondary); font-size: 12px; }

.brief-list, .quote-row { display: grid; gap: 8px; }
.brief-item { padding: 6px 0; border-bottom: 1px solid var(--border-soft); }

@media (max-width: 900px) {
  .asset-strip, .review-grid, .score-row, .heat-grid { grid-template-columns: 1fr; }
}
</style>
