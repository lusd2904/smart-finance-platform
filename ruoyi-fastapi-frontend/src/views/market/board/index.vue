<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>行情台</h2><p>只读缓存报价 · 点入 K 线、详情或 AI 研判</p></div>
      <div class="acts">
        <el-select v-model="market" clearable placeholder="市场" style="width:110px" @change="() => loadAll(false)">
          <el-option label="全部" value="" />
          <el-option label="美股" value="US" />
          <el-option label="港股" value="HK" />
          <el-option label="A股" value="CN" />
        </el-select>
        <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:160px" />
        <el-button type="primary" :loading="loading" icon="Refresh" @click="() => loadAll(false)">刷新</el-button>
        <el-button type="success" icon="Monitor" @click="router.push('/trade/terminal')">专业交易终端</el-button>
      </div>
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
      <el-table-column prop="market" label="市场" width="80"/>
      <el-table-column prop="symbol" label="代码" width="110" sortable="custom"/>
      <el-table-column prop="name" label="名称" min-width="120"/>
      <el-table-column prop="price" label="最新价" width="110" sortable="custom"/>
      <el-table-column prop="change" label="涨跌幅%" width="120" sortable="custom">
        <template #default="{row}"><span :class="row.up?'up':'down'">{{ row.changeText }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{row}">
          <el-button link type="primary" @click="goKline(row)">K线</el-button>
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button link type="primary" @click="goAi(row)">AI研判</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="MarketBoard">
import { getBoardQuotes } from '@/api/market'
import { applyQuotePatch, getQuotesHub } from '@/composables/useMarketQuotesWs'
const router=useRouter()
const loading=ref(false)
const rows=ref([])
const indices=ref([])
const market=ref('')
const keyword=ref('')
const sortProp=ref('change')
const sortOrder=ref('descending')
let quoteTimer=null
let unsubQuotes=null
const sorted=computed(()=>{
  const kw=String(keyword.value||'').trim().toUpperCase()
  let arr=[...rows.value]
  if(kw) arr=arr.filter(r=>String(r.symbol||'').toUpperCase().includes(kw)||String(r.name||'').toUpperCase().includes(kw))
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
function goAi(r){ router.push({path:'/market/ai-workbench', query:{symbol:r.symbol, market:r.market||'US'}}) }
function normalizeMarket(m){
  const u=String(m||'US').trim().toUpperCase()
  if(u==='HK'||u==='HKEX') return 'HK'
  if(u==='CN'||u==='A'||u==='SH'||u==='SZ'||u==='CSI') return 'CN'
  return 'US'
}
function isIndexRow(row){
  const cat=String(row&&(row.category||row.kind||row.type)||'').toLowerCase()
  if(cat==='index') return true
  const sym=String(row&&row.symbol||'')
  return sym.startsWith('^')||sym.startsWith('.')
}
function formatQuote(item){
  const rawPrice=item.last!=null?item.last:item.price
  const price=rawPrice==null?null:Number(rawPrice)
  const change=item.changePct!=null?item.changePct:(item.changeRate==null?item.change:item.changeRate)
  const nChange=Number(change)
  const hasChange=change!=null&&!Number.isNaN(nChange)
  return {
    ...item,
    market:normalizeMarket(item.market),
    price:price==null||Number.isNaN(price)?null:price.toFixed(2),
    last:price==null||Number.isNaN(price)?item.last:price,
    change:hasChange?nChange:change,
    changeRate:hasChange?nChange:item.changeRate,
    changePct:hasChange?nChange:item.changePct,
    changeText:hasChange?`${nChange>=0?'+':''}${nChange.toFixed(2)}%`:(item.changeText||'--'),
    up:hasChange?nChange>=0:(item.up==null?true:!!item.up)
  }
}
function dropQuoteSub(){
  if(unsubQuotes){ unsubQuotes(); unsubQuotes=null }
}
function syncQuoteSub(){
  dropQuoteSub()
  const pairs=(rows.value||[]).filter(r=>r&&r.symbol&&!isIndexRow(r)).map(r=>({symbol:r.symbol, market:normalizeMarket(r.market)}))
  if(!pairs.length) return
  unsubQuotes=getQuotesHub().subscribeQuotes(pairs, (payload)=>{
    rows.value=applyQuotePatch(rows.value, (payload&&payload.items)||[]).map(formatQuote)
  })
}
async function loadAll(silent=false){
  if(!silent) loading.value=true
  try{
    const res=await getBoardQuotes({ market: market.value || undefined })
    const payload=res.data||{}
    indices.value=(payload.indices||[]).map(formatQuote)
    rows.value=(payload.rows||payload.quotes||[]).map(formatQuote)
    syncQuoteSub()
  } finally { if(!silent) loading.value=false }
}
function stopQuoteTimer(){
  if(quoteTimer){ clearInterval(quoteTimer); quoteTimer=null }
}
function startQuoteTimer(){
  stopQuoteTimer()
  quoteTimer=setInterval(()=>loadAll(true), 60000)
}
function handleVisibility(){
  if(document.visibilityState==='visible'){
    if(!quoteTimer) startQuoteTimer()
    syncQuoteSub()
  } else {
    stopQuoteTimer()
    dropQuoteSub()
  }
}
onMounted(()=>{
  loadAll()
  startQuoteTimer()
  document.addEventListener('visibilitychange', handleVisibility)
})
onActivated(()=>{
  startQuoteTimer()
  if(!rows.value.length) loadAll(true)
  else syncQuoteSub()
})
onDeactivated(()=>{ stopQuoteTimer(); dropQuoteSub() })
onBeforeUnmount(()=>{
  document.removeEventListener('visibilitychange', handleVisibility)
  stopQuoteTimer()
  dropQuoteSub()
})
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.mb16{margin-bottom:16px}
.idx-card{background:var(--surface-card,#fff);border:1px solid var(--border-soft);border-radius:14px;padding:14px;margin-bottom:10px;cursor:pointer}
.idx-card .name{font-weight:600;color:var(--text-emphasis)} .sym{font-size:12px;color:var(--text-muted);margin-left:6px}
.price{font-size:24px;font-weight:700;margin:6px 0} .up{color:var(--stat-up,#dc2626)} .down{color:var(--stat-down,#059669)}
</style>
