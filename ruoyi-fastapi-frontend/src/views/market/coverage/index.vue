<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>行情历史覆盖</h2><p>目标标的 Influx 最新交易日与缺失 · HistoryCoverage</p></div>
      <div class="acts">
        <el-select v-model="market" clearable placeholder="市场" style="width:100px" @change="noop">
          <el-option label="全部" value=""/>
          <el-option label="US" value="US"/><el-option label="HK" value="HK"/><el-option label="CN" value="CN"/>
        </el-select>
        <el-select v-model="statusFilter" clearable placeholder="状态" style="width:110px">
          <el-option label="全部" value=""/><el-option label="已覆盖" value="ok"/><el-option label="缺失" value="missing"/>
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">刷新检测</el-button>
      </div>
    </div>
    <el-row :gutter="12" class="mb16">
      <el-col :span="6"><div class="mini"><div class="n">{{ stats.total }}</div><div class="l">目标</div></div></el-col>
      <el-col :span="6"><div class="mini"><div class="n">{{ stats.covered }}</div><div class="l">已覆盖</div></div></el-col>
      <el-col :span="6"><div class="mini"><div class="n">{{ stats.missing }}</div><div class="l">缺失</div></div></el-col>
      <el-col :span="6"><div class="mini"><div class="n">{{ stats.pct }}%</div><div class="l">覆盖率</div></div></el-col>
    </el-row>
    <el-table v-loading="loading" :data="filtered" stripe>
      <el-table-column prop="symbol" label="代码" width="110"/>
      <el-table-column prop="name" label="名称" min-width="120"/>
      <el-table-column prop="market" label="市场" width="80"/>
      <el-table-column prop="category" label="类别" width="100"/>
      <el-table-column prop="latestDate" label="最新日" width="120"/>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{row}"><el-tag :type="row.covered?'success':'danger'" size="small">{{ row.covered?'OK':'缺失' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{row}">
          <el-button link type="primary" @click="$router.push({path:'/market/kline', query:{symbol:row.symbol, market:row.market}})">K线</el-button>
          <el-button link type="primary" @click="$router.push({path:'/market/tradingview', query:{symbol:row.symbol, market:row.market}})">高级图</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
<script setup name="MarketCoverage">
import { getHistoryCoverage } from '@/api/trade'
const loading=ref(false); const data=ref({items:[]}); const market=ref(''); const statusFilter=ref('')
const filtered=computed(()=>{
  let rows=data.value.items||[]
  if(market.value) rows=rows.filter(r=>r.market===market.value)
  if(statusFilter.value==='ok') rows=rows.filter(r=>r.covered)
  if(statusFilter.value==='missing') rows=rows.filter(r=>!r.covered)
  return rows
})
const stats=computed(()=>{
  const rows=filtered.value
  const covered=rows.filter(r=>r.covered).length
  const total=rows.length
  return { total, covered, missing: total-covered, pct: total? +(covered/total*100).toFixed(1):0 }
})
function noop(){}
async function load(){ loading.value=true; try{ data.value=(await getHistoryCoverage()).data||{items:[]} } finally{ loading.value=false } }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.mb16{margin-bottom:16px}
.mini{background:var(--surface-card);border:1px solid var(--border-soft);border-radius:12px;padding:12px}
.n{font-size:22px;font-weight:700;color:var(--text-emphasis)} .l{font-size:12px;color:var(--text-muted)}
</style>
