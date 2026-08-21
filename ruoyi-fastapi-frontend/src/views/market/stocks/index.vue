<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>分市场标的</h2><p>覆盖美股 / 港股 / A股目标池，支持搜索与盘中报价</p></div>
      <div class="acts">
        <el-radio-group v-model="market" @change="() => loadData(false)">
          <el-radio-button label="US">美股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="CN">A股</el-radio-button>
        </el-radio-group>
        <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:180px" @keyup.enter="() => loadData(false)" @clear="() => loadData(false)" />
        <el-button type="primary" :loading="loading" icon="Refresh" @click="() => loadData(false)">刷新</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="symbol" label="代码" width="120"/>
      <el-table-column prop="name" label="名称" min-width="140"/>
      <el-table-column prop="category" label="分类" width="120"/>
      <el-table-column label="最新价" width="110" align="right">
        <template #default="{row}">{{ formatNum(row.last) }}</template>
      </el-table-column>
      <el-table-column label="涨跌" width="110" align="right">
        <template #default="{row}">
          <span :class="chgClass(row.changeRate)">{{ formatPct(row.changeRate) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="market" label="市场" width="80"/>
      <el-table-column label="操作" width="180">
        <template #default="{row}">
          <el-button link type="primary" @click="goKline(row)">K线</el-button>
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button link type="primary" @click="goAi(row)">AI研判</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="MarketStocks">
import { listInstrument, getBoardQuotes } from '@/api/market'
const router = useRouter()
const market = ref('US')
const keyword = ref('')
const loading = ref(false)
const list = ref([])
let quoteTimer = null
function goKline(row){ router.push({ path:'/market/kline', query:{ symbol:row.symbol, market:row.market||market.value }}) }
function goDetail(row){ router.push({ path:'/market/symbol', query:{ symbol:row.symbol, market:row.market||market.value }}) }
function goAi(row){ router.push({ path:'/market/ai-workbench', query:{ symbol:row.symbol, market:row.market||market.value }}) }
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
async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const [instRes, quoteRes] = await Promise.all([
      listInstrument({ market: market.value, keyword: keyword.value || undefined }),
      getBoardQuotes({ market: market.value })
    ])
    const rows = instRes.data || instRes.rows || []
    const quotes = (quoteRes.data || {}).rows || (quoteRes.data || {}).quotes || []
    const quoteMap = {}
    quotes.forEach(q => { if (q.symbol) quoteMap[q.symbol] = q })
    list.value = (Array.isArray(rows) ? rows : []).map(r => {
      const q = quoteMap[r.symbol] || {}
      return {
        ...r,
        last: q.last != null ? q.last : q.price,
        changeRate: q.changeRate != null ? q.changeRate : q.change
      }
    })
  } finally {
    if (!silent) loading.value = false
  }
}
onMounted(() => {
  loadData()
  quoteTimer = setInterval(() => loadData(true), 8000)
})
onBeforeUnmount(() => { if (quoteTimer) clearInterval(quoteTimer) })
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)}
.page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.up{color:var(--stat-up,#dc2626);font-weight:600}
.down{color:var(--stat-down,#059669);font-weight:600}
</style>
