<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>持仓</h2><p>长桥真实持仓（需配置凭证）</p></div>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button></div>
    <el-alert v-if="msg" :title="msg" type="info" show-icon class="mb16"/>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="symbol" label="代码" width="120"/>
      <el-table-column prop="symbolName" label="名称" min-width="140"/>
      <el-table-column prop="quantity" label="数量" width="100"/>
      <el-table-column prop="availableQuantity" label="可用" width="100"/>
      <el-table-column prop="costPrice" label="成本价" width="100"/>
      <el-table-column prop="currency" label="币种" width="80"/>
      <el-table-column label="操作" width="120">
        <template #default="{row}">
          <el-button link type="primary" @click="$router.push({path:'/trade/trading', query:{symbol:row.symbol}})">交易</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="TradePositions">
import { getTradePositions } from '@/api/trade'
const loading=ref(false); const list=ref([]); const msg=ref('')
async function load(){
  loading.value=true
  try{
    const res=await getTradePositions(); const d=res.data||{}
    list.value=d.positions||[]; msg.value=d.message||(d.configured===false?'未配置长桥凭证':'')
  } finally { loading.value=false }
}
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.mb16{margin-bottom:16px}
</style>
