<template>
  <div class="app-container market-universe">
    <div class="hero-card mb16">
      <div class="hero-left">
        <div class="hero-title">全部股票</div>
        <div class="hero-sub">美股 / 港股 / A 股全市场代码 · 分页浏览 · 点入 K 线与详情</div>
      </div>
      <div class="hero-actions">
        <el-radio-group v-model="market" class="market-switch" @change="onFilterChange">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="CN">A股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="US">美股</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="keyword"
          clearable
          placeholder="代码 / 名称"
          prefix-icon="Search"
          style="width: 200px"
          @keyup.enter="onFilterChange"
          @clear="onFilterChange"
        />
        <el-button type="primary" icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="mb16">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.key">
        <div class="stat-card" :class="{ active: market === card.market }" @click="pickMarket(card.market)">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-sub">{{ card.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">{{ tableTitle }}</span>
          <span class="panel-sub">最新价取自本地日K，非盘中实时</span>
        </div>
      </template>
      <el-table v-loading="loading" :data="list" stripe empty-text="暂无标的">
        <el-table-column prop="market" label="市场" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ marketLabel(row.market) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="128">
          <template #default="{ row }"><span class="mono">{{ row.symbol }}</span></template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ formatNum(row.price) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110" align="right">
          <template #default="{ row }">
            <span class="chg-cell" :class="chgClass(row.changeRate)">{{ formatPct(row.changeRate) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="tradeDate" label="最新日" width="118" />
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goKline(row)">K线</el-button>
            <el-button link type="primary" @click="goDetail(row)">详情</el-button>
            <el-button
              v-if="adding !== row.symbol"
              link
              type="success"
              @click="addWatch(row)"
            >加自选</el-button>
            <el-tag v-else size="small" type="success" effect="plain">加入中</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="pageNum"
        v-model:limit="pageSize"
        @pagination="loadData"
      />
    </el-card>
  </div>
</template>

<script setup name="MarketStocks">
import { listInstrumentUniverse, addMarketWatchlist } from '@/api/market'

const route = useRoute()
const router = useRouter()
const { proxy } = getCurrentInstance()

const CAT = {
  listed: '全市场',
  index: '指数',
  mag7: '七巨头',
  star: '明星',
  semiconductor: '半导体',
  software: '软件',
  etf: 'ETF',
  finance: '金融',
  healthcare: '医疗',
  energy: '能源',
  consumer: '消费'
}

const market = ref('')
const keyword = ref('')
const loading = ref(false)
const list = ref([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(50)
const counts = ref({ US: 0, HK: 0, CN: 0, total: 0 })
const adding = ref('')

const tableTitle = computed(() => {
  const label = market.value ? marketLabel(market.value) : '三市场'
  return `${label} · ${total.value.toLocaleString()} 只`
})

const statCards = computed(() => [
  { key: 'all', market: '', label: '合计', value: fmtCount(counts.value.total), sub: '三市场入库代码' },
  { key: 'cn', market: 'CN', label: 'A股', value: fmtCount(counts.value.CN), sub: '沪深北' },
  { key: 'hk', market: 'HK', label: '港股', value: fmtCount(counts.value.HK), sub: '港交所' },
  { key: 'us', market: 'US', label: '美股', value: fmtCount(counts.value.US), sub: 'NYSE / NASDAQ' }
])

function fmtCount(n) {
  return Number(n || 0).toLocaleString()
}

function marketLabel(code) {
  return { US: '美股', HK: '港股', CN: 'A股' }[code] || code || '--'
}

function categoryLabel(cat) {
  if (!cat) return '--'
  return CAT[cat] || cat
}

function formatNum(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  return Number.isNaN(n) ? '--' : n.toFixed(2)
}

function formatPct(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  if (Number.isNaN(n)) return '--'
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}

function chgClass(v) {
  const n = Number(v)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}

function goKline(row) {
  router.push({ path: '/market/kline', query: { symbol: row.symbol, market: row.market || 'US' } })
}

function goDetail(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } })
}

function pickMarket(code) {
  if (market.value === code) return
  market.value = code
  onFilterChange()
}

function onFilterChange() {
  pageNum.value = 1
  loadData()
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: row.market || 'US', note: '全部股票' })
    proxy?.$modal?.msgSuccess?.('已加入自选')
  } catch (e) {
    /* request 拦截器已提示 */
  } finally {
    adding.value = ''
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await listInstrumentUniverse({
      market: market.value || undefined,
      keyword: keyword.value || undefined,
      pageNum: pageNum.value,
      pageSize: pageSize.value
    })
    list.value = res.rows || res.data?.rows || []
    total.value = Number(res.total || 0)
    if (res.counts) counts.value = { US: 0, HK: 0, CN: 0, total: 0, ...res.counts }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const qm = String(route.query.market || '').toUpperCase()
  if (['US', 'HK', 'CN'].includes(qm)) market.value = qm
  loadData()
})
</script>

<style scoped lang="scss">
.market-universe {
  --mc-up: var(--stat-up, #dc2626);
  --mc-down: var(--stat-down, #059669);
}

.mb16 { margin-bottom: 14px; }

.mono {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 13px;
}

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

  .hero-title { font-size: 22px; font-weight: 700; }
  .hero-sub { margin-top: 4px; font-size: 13px; opacity: 0.88; }
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.market-switch :deep(.el-radio-button__inner) {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  border: none;
}

.market-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: #fff;
  color: #4f46e5;
}

.stat-card {
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  border-radius: 14px;
  padding: 14px 16px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover, &.active {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(79, 70, 229, 0.12);
    border-color: #c7d2fe;
  }

  .stat-label { color: var(--text-muted, #909399); font-size: 12px; }
  .stat-value { font-size: 22px; font-weight: 700; color: var(--text-emphasis, #303133); }
  .stat-sub { font-size: 11px; color: var(--text-muted, #909399); }
}

.panel-card {
  border-radius: 14px;
  border: 1px solid var(--border-soft, #eef2ff);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  .panel-title { font-size: 15px; font-weight: 600; }
  .panel-sub { font-size: 12px; color: var(--text-muted, #909399); }
}

.chg-cell.up { color: var(--mc-up); font-weight: 600; }
.chg-cell.down { color: var(--mc-down); font-weight: 600; }
</style>
