<template>
  <div class="app-container pick-page">
    <div class="hero-card mb16">
      <div class="hero-left">
        <div class="hero-title">智能选股</div>
        <div class="hero-sub">
          指标 + 舆情 + 开盘指数 · 休市市场自动去掉实时指数
          <el-tag v-if="latest.updatedAt" size="small" effect="plain" class="asof-tag">{{ latest.updatedAt }}</el-tag>
        </div>
      </div>
      <div class="hero-actions">
        <el-radio-group v-model="market" size="small" @change="loadLatest">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="CN">A股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="US">美股</el-radio-button>
        </el-radio-group>
        <el-button @click="refreshMood" :loading="moodLoading">刷新情绪</el-button>
        <el-button type="primary" :loading="runLoading" @click="handleRun" v-hasPermi="['market:picks:run', 'market:ai:analyze']">生成选股单</el-button>
        <el-button icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-alert class="mb16" type="info" show-icon :closable="false" :title="mood.hint || '定时任务可在「任务中心 / 自动分析任务」改 cron 与启停。'" />

    <el-row :gutter="12" class="mb16">
      <el-col :xs="24" :sm="8" v-for="card in marketCards" :key="card.market">
        <div class="session-card" :class="{ open: card.open }">
          <div class="session-top">
            <span class="session-name">{{ card.label }}</span>
            <el-tag size="small" :type="card.open ? 'success' : 'info'" effect="plain">{{ card.open ? '开盘' : '休市' }}</el-tag>
          </div>
          <div class="session-score">舆情 {{ card.sentText }}</div>
          <div class="session-sub">{{ card.indexText }}</div>
          <div class="session-time">当地 {{ card.localTime || '--' }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card v-if="headlines.length" shadow="never" class="panel-card mb16">
      <template #header><span class="panel-title">最新舆情标题</span></template>
      <div class="headline" v-for="h in headlines" :key="h.title">
        <span class="h-src">{{ h.source }}</span>
        <span>{{ h.title }}</span>
      </div>
    </el-card>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">{{ tableTitle }}</span>
          <span class="panel-sub">{{ latest.message || '入选名单结合因子打分、舆情与开盘指数' }}</span>
        </div>
      </template>
      <el-table v-loading="loading" :data="items" stripe empty-text="暂无选股单，点击「生成选股单」或等待收盘任务">
        <el-table-column prop="rankNo" label="#" width="52" />
        <el-table-column prop="market" label="市场" width="76" align="center">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ marketLabel(row.market) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }"><span class="mono">{{ row.symbol }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="110" show-overflow-tooltip />
        <el-table-column label="最新价" width="100" align="right">
          <template #default="{ row }"><span class="mono">{{ fmtNum(row.price) }}</span></template>
        </el-table-column>
        <el-table-column label="涨跌" width="90" align="right">
          <template #default="{ row }"><span :class="chgClass(row.changePct)">{{ fmtPct(row.changePct) }}</span></template>
        </el-table-column>
        <el-table-column prop="pickScore" label="选股分" width="88" align="right" />
        <el-table-column prop="recommendation" label="建议" width="88" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="recoType(row.recommendation)">{{ row.recommendation || '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goKline(row)">K线</el-button>
            <el-button link type="primary" @click="goDetail(row)">详情</el-button>
            <el-button v-if="!row.inWatchlist" link type="success" @click="addWatch(row)">加自选</el-button>
            <el-tag v-else size="small" type="success" effect="plain">已自选</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="MarketRecommendations">
import {
  addMarketWatchlist,
  getStockPickLatest,
  getStockPickMood,
  refreshStockPickMood,
  runStockPick
} from '@/api/market'

const router = useRouter()
const { proxy } = getCurrentInstance()
const market = ref('')
const loading = ref(false)
const moodLoading = ref(false)
const runLoading = ref(false)
const mood = ref({ sessions: {}, sentiment: {}, indices: [], headlines: [], openMarkets: [], hint: '' })
const latest = ref({ items: [], message: '', empty: true })
const adding = ref('')

const items = computed(() => latest.value.items || [])
const headlines = computed(() => (mood.value.headlines || []).slice(0, 6))
const tableTitle = computed(() => {
  const n = items.value.length
  const date = latest.value.tradeDate || ''
  return `${date || '选股单'} · ${n} 只`
})

const marketCards = computed(() => {
  const sessions = mood.value.sessions || {}
  const sent = mood.value.sentiment || {}
  const indices = mood.value.indices || []
  const scoreMap = { US: sent.usScore, HK: sent.hkScore, CN: sent.aScore }
  const dirMap = { US: sent.usDirection, HK: sent.hkDirection, CN: sent.aDirection }
  return ['CN', 'HK', 'US'].map((m) => {
    const sess = sessions[m] || {}
    const live = indices.filter(i => i.market === m)
    const indexText = live.length
      ? live.map(i => `${i.name} ${fmtPct(i.changePct)}`).join(' · ')
      : (sess.open ? '指数暂无' : '休市，已去掉实时指数')
    return {
      market: m,
      label: marketLabel(m),
      open: !!sess.open,
      localTime: sess.localTime,
      sentText: `${dirMap[m] || '—'} ${scoreMap[m] ?? '--'}`,
      indexText
    }
  })
})

function marketLabel(code) {
  return { US: '美股', HK: '港股', CN: 'A股' }[code] || code || '--'
}
function fmtNum(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}
function fmtPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function chgClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}
function recoType(v) {
  if (v === '买入' || v === '关注') return 'danger'
  if (v === '回避') return 'success'
  return 'info'
}
function goKline(row) {
  router.push({ path: '/market/kline', query: { symbol: row.symbol, market: row.market || 'US' } })
}
function goDetail(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } })
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: row.market || 'US', note: '智能选股' })
    row.inWatchlist = true
    proxy?.$modal?.msgSuccess?.('已加入自选')
  } finally {
    adding.value = ''
  }
}

async function loadMood() {
  const res = await getStockPickMood()
  mood.value = res.data || mood.value
}

async function loadLatest() {
  loading.value = true
  try {
    const res = await getStockPickLatest({ market: market.value || undefined })
    latest.value = res.data || { items: [], empty: true }
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  await Promise.all([loadMood(), loadLatest()])
}

async function refreshMood() {
  moodLoading.value = true
  try {
    const res = await refreshStockPickMood()
    proxy?.$modal?.msgSuccess?.(res.msg || '已排队刷新舆情')
    setTimeout(loadMood, 2500)
  } finally {
    moodLoading.value = false
  }
}

async function handleRun() {
  runLoading.value = true
  try {
    const res = await runStockPick()
    proxy?.$modal?.msgSuccess?.(res.msg || '已提交')
    if (res.data && res.data.items) {
      latest.value = res.data
    } else {
      setTimeout(loadLatest, 3000)
    }
  } finally {
    runLoading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.pick-page { --mc-up: var(--stat-up, #dc2626); --mc-down: var(--stat-down, #059669); }
.mb16 { margin-bottom: 14px; }
.mono { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 13px; }
.hero-card {
  display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 20px 24px; border-radius: 16px; color: #fff;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%);
  box-shadow: 0 12px 30px rgba(79, 70, 229, 0.22);
  .hero-title { font-size: 22px; font-weight: 700; }
  .hero-sub { margin-top: 4px; font-size: 13px; opacity: 0.9; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .asof-tag { border: none; background: rgba(255,255,255,.18); color: #fff; }
}
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.session-card {
  background: var(--surface-card, #fff); border: 1px solid var(--border-soft, #eef2ff);
  border-radius: 14px; padding: 14px 16px;
  &.open { border-color: #a7f3d0; }
}
.session-top { display: flex; justify-content: space-between; align-items: center; }
.session-name { font-weight: 700; }
.session-score { margin-top: 8px; font-size: 16px; font-weight: 600; }
.session-sub, .session-time { margin-top: 4px; font-size: 12px; color: var(--text-muted, #909399); }
.panel-card { border-radius: 14px; }
.panel-header { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.panel-title { font-weight: 600; }
.panel-sub { font-size: 12px; color: var(--text-muted, #909399); }
.headline { display: flex; gap: 10px; padding: 6px 0; font-size: 13px; }
.h-src { color: #94a3b8; min-width: 72px; }
.up { color: var(--mc-up); font-weight: 600; }
.down { color: var(--mc-down); font-weight: 600; }
</style>
