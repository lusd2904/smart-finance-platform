<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>策略回测</h2><p>基于 Influx 日K 的 MA5/MA20 简易交叉回测</p></div></div>
    <el-form :inline="true" class="mb16">
      <el-form-item label="标的"><el-input v-model="form.symbol" style="width:120px"/></el-form-item>
      <el-form-item label="市场">
        <el-select v-model="form.market" style="width:100px"><el-option label="US" value="US"/><el-option label="HK" value="HK"/><el-option label="CN" value="CN"/></el-select>
      </el-form-item>
      <el-form-item label="天数"><el-input-number v-model="form.days" :min="60" :max="500"/></el-form-item>
      <el-form-item><el-button type="primary" :loading="running" @click="run">运行回测</el-button></el-form-item>
    </el-form>
    <el-row :gutter="16">
      <el-col :md="10" :xs="24">
        <el-card shadow="never"><template #header>历史回测</template>
          <el-table :data="list" size="small" @row-click="show">
            <el-table-column prop="symbol" label="标的" width="90"/>
            <el-table-column prop="returnPct" label="收益%" width="90"/>
            <el-table-column prop="trades" label="交易" width="70"/>
            <el-table-column prop="createTime" label="时间" min-width="140"/>
          </el-table>
        </el-card>
      </el-col>
      <el-col :md="14" :xs="24">
        <el-card shadow="never" v-loading="running"><template #header>权益曲线 · {{ current.symbol || '-' }} · {{ current.returnPct ?? '--' }}%</template>
          <div ref="chartRef" style="height:320px"></div>
          <div class="meta" v-if="current.message">{{ current.message }} · 终值 {{ current.finalEquity }} · 交易 {{ current.trades }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup name="TradeBacktest">
import echarts from '@/utils/echarts'
import { runBacktest, listBacktests, getBacktest } from '@/api/trade'
import { applyChartTheme } from '@/utils/echartsTheme'
const {proxy}=getCurrentInstance()
const form=ref({symbol:'AAPL', market:'US', days:120})
const running=ref(false); const list=ref([]); const current=ref({}); const chartRef=ref(); let chart
async function refreshList(){ const res=await listBacktests(); list.value=res.data||[] }
async function run(){
  running.value=true
  try{
    const res=await runBacktest(form.value); current.value=res.data||{}
    if(current.value.ok===false) proxy.$modal.msgError(current.value.message||'失败')
    else proxy.$modal.msgSuccess(current.value.message||'完成')
    render(); await refreshList()
  } finally { running.value=false }
}
async function show(row){
  const res=await getBacktest(row.id); current.value=res.data||row; render()
}
function render(){
  if(!chartRef.value) return
  if(!chart) chart=echarts.init(chartRef.value)
  const eq=current.value.equity||[]
  const opt=applyChartTheme({
    tooltip:{trigger:'axis'},
    xAxis:{type:'category', data:eq.map(i=>i.date)},
    yAxis:{type:'value', scale:true},
    series:[{type:'line', smooth:true, data:eq.map(i=>i.equity), areaStyle:{opacity:0.08}, itemStyle:{color:'#6366f1'}}]
  })
  chart.setOption(opt, true)
}
onMounted(async()=>{ await refreshList(); window.addEventListener('resize', ()=>chart&&chart.resize()) })
onBeforeUnmount(()=>{ chart&&chart.dispose() })
</script>
<style scoped>
.page-hero{margin-bottom:12px} .page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.mb16{margin-bottom:16px} .meta{margin-top:10px;font-size:13px;color:var(--text-muted)}
</style>
