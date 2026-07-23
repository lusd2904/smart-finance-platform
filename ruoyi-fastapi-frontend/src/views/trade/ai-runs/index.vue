<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>AI 自动交易台账</h2><p>调度运行记录（可与策略扫描联动扩展）</p></div>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button></div>
    <el-table v-loading="loading" :data="list" stripe>
      <el-table-column prop="id" label="ID" width="80"/>
      <el-table-column prop="symbol" label="标的" width="100"/>
      <el-table-column prop="signal" label="信号" width="100"/>
      <el-table-column prop="status" label="状态" width="110"/>
      <el-table-column prop="confidence" label="置信度" width="100"/>
      <el-table-column prop="note" label="备注" min-width="200"/>
      <el-table-column prop="createTime" label="时间" width="170"/>
    </el-table>
  </div>
</template>
<script setup name="TradeAiRuns">
import { listAiTradeRuns } from '@/api/trade'
const loading=ref(false); const list=ref([])
async function load(){ loading.value=true; try{ const res=await listAiTradeRuns(); list.value=res.data||[] } finally{ loading.value=false } }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
</style>
