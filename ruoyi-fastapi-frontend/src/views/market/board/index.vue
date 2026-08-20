<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>全市场行情台</h2><p>指数快照 + 目标池涨跌排序</p></div>
      <el-button type="primary" :loading="loading" icon="Refresh" @click="loadAll">刷新</el-button>
    </div>
    <el-row :gutter="12" class="mb16">
      <el-col :xs="24" :sm="8" v-for="ix in indices" :key="ix.symbol">
        <div class="idx-card" @click="goKline(ix)">
          <div class="name">{{ ix.name }} <span class="sym">{{ ix.symbol }}</span></div>
          <div class="price" :class="ix.up?'up':'down'">{{ ix.price ?? '--' }}</div>
          <div class="chg" :class="ix.up?'up':'down'">{{ ix.changeText || '--' }}</div>
        </div>
      </el-col>
    </el-row>
    <el-table v-loading="loading" :data="sorted" stripe @sort-change="onSort">
      <el-table-column prop="symbol" label="代码" width="110" sortable="custom"/>
      <el-table-column prop="name" label="名称" min-width="120"/>
      <el-table-column prop="price" label="最新价" width="110" sortable="custom"/>
      <el-table-column prop="change" label="涨跌幅%" width="120" sortable="custom">
        <template #default="{row}"><span :class="row.up?'up':'down'">{{ row.changeText }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{row}">
          <el-button link type="primary" @click="goKline(row)">K线</el-button>
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="MarketBoard">
import { getBoardQuotes } from '@/api/market'
const router=useRouter()
const loading=ref(false)
const rows=ref([])
const indices=ref([])
const sortProp=ref('change')
const sortOrder=ref('descending')
const sorted=computed(()=>{
  const arr=[...rows.value]
  const p=sortProp.value, o=sortOrder.value
  if(!p||!o) return arr
  arr.sort((a,b)=>{
    const av=a[p]==null?-999:Number(a[p]); const bv=b[p]==null?-999:Number(b[p])
    return o==='ascending'?av-bv:bv-av
  })
  return arr
})
function onSort({prop,order}){ sortProp.value=prop; sortOrder.value=order }
function goKline(r){ router.push({path:'/market/kline', query:{symbol:r.symbol, market:r.market||'US'}}) }
function goDetail(r){ router.push({path:'/market/symbol', query:{symbol:r.symbol, market:r.market||'US'}}) }
function formatQuote(item){
  const price = item.price == null ? null : Number(item.price)
  const change = item.changeRate == null ? item.change : item.changeRate
  return {
    ...item,
    price: price == null || Number.isNaN(price) ? null : price.toFixed(2),
    change,
    changeText: item.changeText || (change == null ? '--' : `${change >= 0 ? '+' : ''}${Number(change).toFixed(2)}%`),
    up: item.up == null ? true : !!item.up
  }
}
async function loadAll(){
  loading.value=true
  try{
    const res=await getBoardQuotes()
    const payload=res.data||{}
    indices.value=(payload.indices||[]).map(formatQuote)
    rows.value=(payload.rows||payload.quotes||[]).map(formatQuote)
  } finally { loading.value=false }
}
onMounted(loadAll)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.mb16{margin-bottom:16px}
.idx-card{background:var(--surface-card,#fff);border:1px solid var(--border-soft);border-radius:14px;padding:14px;margin-bottom:10px;cursor:pointer}
.idx-card .name{font-weight:600;color:var(--text-emphasis)} .sym{font-size:12px;color:var(--text-muted);margin-left:6px}
.price{font-size:24px;font-weight:700;margin:6px 0} .up{color:var(--stat-up,#dc2626)} .down{color:var(--stat-down,#059669)}
</style>
