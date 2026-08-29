<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>持仓</h2><p>长桥真实持仓（需配置凭证）</p></div>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button></div>
    <el-alert v-if="msg" :title="msg" type="info" show-icon class="mb16"/>
    <el-table v-loading="loading" :data="list" stripe empty-text="暂无持仓">
      <el-table-column prop="symbol" label="代码" width="120"/>
      <el-table-column prop="symbolName" label="名称" min-width="140"/>
      <el-table-column prop="quantity" label="数量" width="100"/>
      <el-table-column prop="availableQuantity" label="可用" width="100"/>
      <el-table-column prop="costPrice" label="成本价" width="100"/>
      <el-table-column label="现价" width="100">
        <template #default="{row}">{{ fmtNum(row.last) }}</template>
      </el-table-column>
      <el-table-column label="涨跌%" width="90">
        <template #default="{row}">
          <span :class="chgClass(row.changePct)">{{ fmtPct(row.changePct) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="浮盈%" width="90">
        <template #default="{row}">
          <span :class="chgClass(row.pnlPct)">{{ fmtPct(row.pnlPct) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="currency" label="币种" width="80"/>
      <el-table-column label="操作" width="120">
        <template #default="{row}">
          <el-button link type="primary" @click="$router.push({path:'/trade/terminal', query:{symbol:posPair(row).symbol, market:posPair(row).market}})">交易</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="TradePositions">
import { getTradePositions } from '@/api/trade'
import { getQuotesHub } from '@/composables/useMarketQuotesWs'
const loading=ref(false); const list=ref([]); const msg=ref('')
let unsubQuotes=null
function posPair(row){
  const raw=String((row&&row.symbol)||'').toUpperCase()
  let market=String((row&&row.market)||'US').toUpperCase()
  let symbol=raw
  if(raw.endsWith('.US')){ symbol=raw.slice(0,-3); market='US' }
  else if(raw.endsWith('.HK')){ symbol=raw.slice(0,-3); market='HK' }
  else if(raw.endsWith('.SH')||raw.endsWith('.SZ')||raw.endsWith('.SS')){ symbol=raw.split('.')[0]; market='CN' }
  return {symbol, market}
}
function fmtNum(v){ const n=Number(v); return Number.isFinite(n)?n.toFixed(2):'--' }
function fmtPct(v){ const n=Number(v); if(!Number.isFinite(n)) return '--'; return `${n>0?'+':''}${n.toFixed(2)}%` }
function chgClass(v){ const n=Number(v); if(!Number.isFinite(n)||n===0) return ''; return n>0?'up':'down' }
function dropQuoteSub(){ if(unsubQuotes){ unsubQuotes(); unsubQuotes=null } }
function applyLive(payload){
  const items=(payload&&payload.items)||[]
  if(!items.length) return
  const map=new Map(items.map(q=>[`${String(q.market||'US').toUpperCase()}:${String(q.symbol||'').toUpperCase()}`, q]))
  list.value=list.value.map(row=>{
    const pair=posPair(row)
    const hit=map.get(`${pair.market}:${pair.symbol}`)
    if(!hit||hit.last==null) return row
    const last=Number(hit.last)
    const cost=Number(row.costPrice)
    const chg=hit.changePct??hit.changeRate
    const pnl=cost? (last/cost-1)*100 : row.pnlPct
    return {...row, last, changePct: chg!=null?Number(chg):row.changePct, pnlPct: Number.isFinite(pnl)?pnl:row.pnlPct, quoteSource:'live'}
  })
}
function syncQuoteSub(){
  dropQuoteSub()
  const pairs=list.value.map(posPair).filter(p=>p.symbol)
  if(!pairs.length) return
  unsubQuotes=getQuotesHub().subscribeQuotes(pairs, applyLive)
}
async function load(){
  loading.value=true
  try{
    const res=await getTradePositions(); const d=res.data||{}
    list.value=d.positions||[]; msg.value=d.message||(d.configured===false?'未配置长桥凭证':'')
    syncQuoteSub()
  } finally { loading.value=false }
}
onMounted(load)
onBeforeUnmount(dropQuoteSub)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.mb16{margin-bottom:16px}
.up{color:var(--el-color-danger)}
.down{color:var(--el-color-success)}
</style>
