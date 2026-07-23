<template>
  <div class="app-container stock-pool">
    <div class="page-hero">
      <div>
        <h2>标的股票池</h2>
        <p>目标标的清单 · 分类筛选 · 快速进入 K 线与详情</p>
      </div>
      <div class="hero-actions">
        <el-select v-model="category" clearable placeholder="分类" style="width: 140px" @change="loadData">
          <el-option label="全部" value="" />
          <el-option label="指数" value="index" />
          <el-option label="科技" value="tech" />
          <el-option label="芯片" value="chip" />
          <el-option label="软件" value="software" />
        </el-select>
        <el-input v-model="keyword" clearable placeholder="搜索代码/名称" style="width: 200px" @keyup.enter="filterLocal" />
        <el-button type="primary" icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="stat-row">
      <el-col :span="6"><div class="mini-stat"><div class="n">{{ list.length }}</div><div class="l">池内标的</div></div></el-col>
      <el-col :span="6"><div class="mini-stat"><div class="n">{{ filtered.length }}</div><div class="l">当前筛选</div></div></el-col>
      <el-col :span="6"><div class="mini-stat"><div class="n">{{ quoteReady }}</div><div class="l">已取行情</div></div></el-col>
      <el-col :span="6"><div class="mini-stat"><div class="n">US</div><div class="l">主市场</div></div></el-col>
    </el-row>

    <el-table v-loading="loading" :data="filtered" stripe>
      <el-table-column prop="symbol" label="代码" width="110" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="market" label="市场" width="80" />
      <el-table-column label="最新价" width="110">
        <template #default="{ row }">
          <span :class="row.up ? 'up' : (row.change != null ? 'down' : '')">{{ row.price ?? '--' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="110">
        <template #default="{ row }">
          <span :class="row.up ? 'up' : (row.change != null ? 'down' : '')">{{ row.changeText || '--' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goKline(row)">K线</el-button>
          <el-button link type="primary" @click="goSymbol(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup name="MarketStockPool">
import { listInstrument, getKline } from '@/api/market'

const router = useRouter()
const loading = ref(false)
const list = ref([])
const category = ref('')
const keyword = ref('')
const quoteReady = ref(0)

const filtered = computed(() => {
  const kw = (keyword.value || '').trim().toLowerCase()
  if (!kw) return list.value
  return list.value.filter(i => `${i.symbol} ${i.name} ${i.category}`.toLowerCase().includes(kw))
})

function filterLocal() { /* computed */ }

function goKline(row) {
  router.push({ path: '/market/kline', query: { symbol: row.symbol, market: row.market || 'US' } })
}
function goSymbol(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } })
}

async function enrichQuotes(items) {
  let ready = 0
  const top = items.slice(0, 24)
  for (const item of top) {
    try {
      const res = await getKline({ symbol: item.symbol, market: item.market || 'US', start: '-10d', stop: 'now()' })
      const klines = (res.data && res.data.klines) || []
      if (!klines.length) continue
      const last = klines[klines.length - 1]
      const prev = klines.length > 1 ? klines[klines.length - 2] : null
      const price = Number(last.close)
      let change = null
      if (prev && prev.close) change = ((price - Number(prev.close)) / Number(prev.close)) * 100
      item.price = Number.isFinite(price) ? price.toFixed(2) : '--'
      item.change = change
      item.up = change != null ? change >= 0 : true
      item.changeText = change == null ? '--' : `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`
      ready += 1
    } catch (e) { /* skip */ }
  }
  quoteReady.value = ready
}

async function loadData() {
  loading.value = true
  try {
    const res = await listInstrument(category.value || undefined)
    const rows = res.data || res.rows || []
    list.value = (Array.isArray(rows) ? rows : []).map(r => ({
      symbol: r.symbol,
      name: r.name,
      market: r.market || 'US',
      category: r.category,
      price: null,
      change: null,
      changeText: '',
      up: true
    }))
    await enrichQuotes(list.value)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.page-hero {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  h2 { margin: 0 0 4px; font-size: 20px; }
  p { margin: 0; color: #909399; font-size: 13px; }
}
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.stat-row { margin-bottom: 14px; }
.mini-stat {
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  border-radius: 12px;
  padding: 12px 14px;
  .n { font-size: 22px; font-weight: 700; color: var(--text-emphasis, #0f172a); }
  .l { font-size: 12px; color: var(--text-muted, #94a3b8); margin-top: 2px; }
}
.up { color: var(--stat-up, #dc2626); font-weight: 600; }
.down { color: var(--stat-down, #059669); font-weight: 600; }
.page-hero h2 { color: var(--text-emphasis); }
.page-hero p { color: var(--text-muted); }
</style>
