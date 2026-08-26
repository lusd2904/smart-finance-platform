<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>订单</h2><p>今日 / 历史委托</p></div>
      <div>
        <el-radio-group v-model="scope" @change="load" style="margin-right:10px">
          <el-radio-button label="today">今日</el-radio-button>
          <el-radio-button label="history">历史</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <el-table v-loading="loading" :data="list" stripe>
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
const {proxy}=getCurrentInstance()
const scope=ref('today'); const loading=ref(false); const list=ref([])
async function load(){
  loading.value=true
  try{ const res=await getTradeOrders(scope.value); list.value=(res.data&&res.data.orders)||[] } finally{ loading.value=false }
}
async function cancel(row){
  await proxy.$modal.confirm('确认撤单 '+row.orderId+'？')
  const res=await cancelTradeOrder(row.orderId)
  const d=res.data||{}
  if(d.ok) proxy.$modal.msgSuccess(d.message||'已撤'); else proxy.$modal.msgError(d.message||'失败')
  load()
}
let timer = null
function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
function startTimer() {
  stopTimer()
  timer = setInterval(load, 15000)
}
function handleVisibility() {
  if (document.visibilityState === 'visible') {
    if (!timer) {
      load()
      startTimer()
    }
  } else {
    stopTimer()
  }
}
onMounted(() => {
  load()
  startTimer()
  document.addEventListener('visibilitychange', handleVisibility)
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibility)
  stopTimer()
})
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
</style>
