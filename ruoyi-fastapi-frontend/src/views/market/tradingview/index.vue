
<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>
          高级图表
          <el-tag v-if="liveQuote" size="small" class="live-tag" effect="plain" :type="liveTone">
            LIVE {{ fmtLiveLast(liveQuote.last) }} {{ fmtLivePct(liveQuote.changePct) }}
          </el-tag>
        </h2>
        <p>KLineChart 画线工作区 · MA / VOL / MACD · 最后一根随行情通道更新</p>
      </div>
      <div class="acts">
        <el-select v-model="symbol" filterable style="width:140px" @change="load">
          <el-option v-for="i in instruments" :key="i.symbol" :label="i.symbol" :value="i.symbol"/>
        </el-select>
        <el-select v-model="market" style="width:90px" @change="load">
          <el-option label="US" value="US"/><el-option label="HK" value="HK"/><el-option label="CN" value="CN"/>
        </el-select>
        <el-radio-group v-model="range" @change="load">
          <el-radio-button label="-3m">3M</el-radio-button>
          <el-radio-button label="-1y">1Y</el-radio-button>
          <el-radio-button label="-2y">2Y</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <el-alert
      v-if="fallbackNotice"
      class="mb12"
      type="info"
      show-icon
      :closable="false"
      :title="fallbackNotice"
    />
    <el-card shadow="never" v-loading="loading">
      <KlineProChart :klines="lastKlines" :live-quote="liveQuote" :height="560" />
    </el-card>
  </div>
</template>
<script setup name="MarketTradingView">
import { listInstrument, getKline } from '@/api/market'
import { getQuotesHub } from '@/composables/useMarketQuotesWs'
import KlineProChart from '@/components/KlineProChart/index.vue'
const route=useRoute()
const { proxy } = getCurrentInstance()
const instruments=ref([]); const symbol=ref(route.query.symbol||'AAPL'); const market=ref(route.query.market||'US')
const range=ref('-1y'); const loading=ref(false); const fallbackNotice=ref('')
const liveQuote=ref(null)
const liveTone=computed(()=>{
  const n=Number(liveQuote.value&&liveQuote.value.changePct)
  if(!Number.isFinite(n)) return 'info'
  return n>=0?'danger':'success'
})
const lastKlines=ref([])
let unsubQuotes=null
async function loadInst(){ instruments.value=((await listInstrument()).data)||[] }
function fmtLiveLast(v){ const n=Number(v); return Number.isFinite(n)?n.toFixed(2):'--' }
function fmtLivePct(v){ const n=Number(v); if(!Number.isFinite(n)) return ''; const sign=n>0?'+':''; return `${sign}${n.toFixed(2)}%` }
function lastBarIsRecent(dateStr){
  const day=String(dateStr||'').slice(0,10)
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)) return true
  const t=Date.parse(`${day}T00:00:00`)
  if(!Number.isFinite(t)) return false
  return Date.now()-t < 48*3600*1000
}
function quoteMatches(q, sym, mkt){
  return String(q.symbol||'').toUpperCase()===String(sym||'').toUpperCase()
    && String(q.market||'US').toUpperCase()===String(mkt||'US').toUpperCase()
}
function patchLastBar(quote){
  const last=Number(quote&&quote.last)
  if(!Number.isFinite(last)||!lastKlines.value.length) return
  const idx=lastKlines.value.length-1
  const row=lastKlines.value[idx]
  if(!row) return
  const dated=/^\d{4}-\d{2}-\d{2}/.test(String(row.date||''))
  if(dated && !lastBarIsRecent(row.date)) return
  const prev=Number(row.close)
  if(prev===last) return
  const low=Math.min(Number(row.low), last)
  const high=Math.max(Number(row.high), last)
  lastKlines.value.splice(idx, 1, {...row, close:last, low, high})
}
function dropQuoteSub(){
  if(unsubQuotes){ unsubQuotes(); unsubQuotes=null }
}
function syncQuoteSub(){
  dropQuoteSub()
  const sym=symbol.value
  const mkt=market.value
  if(!sym) return
  unsubQuotes=getQuotesHub().subscribeQuotes([{symbol:sym, market:mkt}], (payload)=>{
    const hit=((payload&&payload.items)||[]).find(q=>quoteMatches(q, symbol.value, market.value))
    if(!hit) return
    liveQuote.value={ last:hit.last, changePct:hit.changePct??hit.changeRate, quoteTime:hit.quoteTime }
    patchLastBar(hit)
  })
}
async function fetchKlines(sym, mkt){
  const res=await getKline({symbol:sym, market:mkt, start:range.value, stop:'now()'})
  return (res.data&&res.data.klines)||[]
}
async function load(){
  loading.value=true
  fallbackNotice.value=''
  liveQuote.value=null
  dropQuoteSub()
  try{
    await proxy.$modal.withLoading('加载中…', async () => {
      let kl=await fetchKlines(symbol.value, market.value)
      lastKlines.value=Array.isArray(kl)?kl.map(k=>({...k})):[]
      if(!kl.length){
        fallbackNotice.value='当前标的暂无真实K线'
      }
    })
  } finally {
    loading.value=false
    syncQuoteSub()
  }
}
onMounted(async()=>{ await loadInst(); await load() })
onBeforeUnmount(()=>{ dropQuoteSub() })
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.mb12{margin-bottom:12px}
.live-tag{margin-left:8px;vertical-align:middle}
</style>
