<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>订单</h2><p>今日 / 历史委托</p></div>
      <div>
        <el-radio-group v-model="scope" @change="loadAndPoll" style="margin-right:10px">
          <el-radio-button label="today">今日</el-radio-button>
          <el-radio-button label="history">历史</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="loading" @click="loadAndPoll">刷新</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="list" stripe empty-text="暂无委托">
      <el-table-column prop="orderId" label="订单号" width="180"/>
      <el-table-column prop="symbol" label="标的" width="110"/>
      <el-table-column prop="side" label="方向" width="80"/>
      <el-table-column prop="orderType" label="类型" width="90"/>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{row}">{{ row.statusLabel || row.status || '--' }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="90"/>
      <el-table-column prop="price" label="价格" width="90"/>
      <el-table-column prop="executedQuantity" label="成交量" width="90"/>
      <el-table-column prop="executedPrice" label="成交价" width="90"/>
      <el-table-column prop="updatedAt" label="更新" min-width="150"/>
      <el-table-column prop="submittedAt" label="提交" min-width="150"/>
      <el-table-column label="操作" width="90">
        <template #default="{row}">
          <el-button link type="danger" @click="cancel(row)" v-if="row.orderId && scope==='today'">撤单</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="TradeOrders">
import { getTradeOrders, cancelTradeOrder } from '@/api/trade'
import { startAdaptivePoll } from '@/composables/useAdaptivePoll'
const {proxy}=getCurrentInstance()
const scope=ref('today'); const loading=ref(false); const list=ref([])
const OPEN_STATUS=new Set(['submitted','new','wait_to_new','waittonew','partial_filled','partialfilled','wait_to_cancel','waittocancel','pending','partial','open','not_reported','notreported'])
const OPEN_LABEL=new Set(['已提交','待成交','待报','待撤','部分成交'])
function orderLooksOpen(row){
  if(!row) return false
  if(row.open===true) return true
  const status=String(row.status||'').trim()
  const compact=status.toLowerCase().replace(/[\s-]/g,'_')
  if(OPEN_STATUS.has(compact)||OPEN_STATUS.has(compact.replace(/_/g,''))) return true
  return OPEN_LABEL.has(String(row.statusLabel||'').trim())
}
function ordersBusy(){ return (list.value||[]).some(orderLooksOpen) }
async function load(silent=false){
  if(!silent) loading.value=true
  try{ const res=await getTradeOrders(scope.value); list.value=(res.data&&res.data.orders)||[] } finally{ if(!silent) loading.value=false }
}
const poll=startAdaptivePoll({ tick:()=>load(true), isBusy:ordersBusy, busyMs:5000, idleMs:30000, hiddenStop:true })
async function loadAndPoll(silent=false){ try{ await load(silent) } finally{ poll.start() } }
async function cancel(row){
  await proxy.$modal.confirm('确认撤单 '+row.orderId+'？')
  const res=await cancelTradeOrder(row.orderId)
  const d=res.data||{}
  if(d.ok) proxy.$modal.msgSuccess(d.message||'已撤'); else proxy.$modal.msgError(d.message||'失败')
  loadAndPoll()
}
onMounted(()=>loadAndPoll())
onActivated(()=>loadAndPoll(true))
onDeactivated(()=>poll.stop())
onBeforeUnmount(()=>poll.stop())
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
</style>
