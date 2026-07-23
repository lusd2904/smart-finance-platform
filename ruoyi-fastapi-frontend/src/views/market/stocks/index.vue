<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>分市场标的</h2><p>US / HK / CN 目标池分市场浏览</p></div>
      <el-radio-group v-model="market" @change="loadData">
        <el-radio-button label="US">美股</el-radio-button>
        <el-radio-button label="HK">港股</el-radio-button>
        <el-radio-button label="CN">A股</el-radio-button>
      </el-radio-group>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="symbol" label="代码" width="120"/>
      <el-table-column prop="name" label="名称" min-width="140"/>
      <el-table-column prop="category" label="分类" width="120"/>
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
import { listInstrument } from '@/api/market'
const router = useRouter()
const market = ref('US')
const loading = ref(false)
const list = ref([])
function goKline(row){ router.push({ path:'/market/kline', query:{ symbol:row.symbol, market:row.market||market.value }}) }
function goDetail(row){ router.push({ path:'/market/symbol', query:{ symbol:row.symbol, market:row.market||market.value }}) }
function goAi(row){ router.push({ path:'/market/ai-workbench', query:{ symbol:row.symbol, market:row.market||market.value }}) }
async function loadData(){
  loading.value=true
  try{
    const res=await listInstrument()
    const rows=res.data||res.rows||[]
    list.value=(Array.isArray(rows)?rows:[]).filter(r=>(r.market||'US').toUpperCase()===market.value)
  } finally { loading.value=false }
}
onMounted(loadData)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)}
.page-hero p{margin:0;color:var(--text-muted);font-size:13px}
</style>
