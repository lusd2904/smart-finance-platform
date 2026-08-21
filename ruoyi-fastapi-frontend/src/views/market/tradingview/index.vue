
<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>高级图表</h2><p>多周期K线 + MA5/20/60（TradingView风格工作区）</p></div>
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
    <el-card shadow="never"><div ref="chartRef" class="chart" v-loading="loading"/></el-card>
  </div>
</template>
<script setup name="MarketTradingView">
import * as echarts from 'echarts'
import { listInstrument, getKline } from '@/api/market'
import { applyChartTheme } from '@/utils/echartsTheme'
const route=useRoute()
const { proxy } = getCurrentInstance()
const instruments=ref([]); const symbol=ref(route.query.symbol||'AAPL'); const market=ref(route.query.market||'US')
const range=ref('-1y'); const loading=ref(false); const chartRef=ref(); const fallbackNotice=ref(''); let chart
async function loadInst(){ instruments.value=((await listInstrument()).data)||[] }
function ma(arr,n){const o=[];for(let i=0;i<arr.length;i++){if(i<n-1){o.push(null);continue}let s=0;for(let j=i-n+1;j<=i;j++)s+=arr[j];o.push(+(s/n).toFixed(2))}return o}
async function fetchKlines(sym, mkt){
  const res=await getKline({symbol:sym, market:mkt, start:range.value, stop:'now()'})
  return (res.data&&res.data.klines)||[]
}
async function load(){
  loading.value=true
  fallbackNotice.value=''
  try{
    await proxy.$modal.withLoading('加载中…', async () => {
      let kl=await fetchKlines(symbol.value, market.value)
      if(!kl.length && (symbol.value||'').toUpperCase() !== 'AAPL'){
        const aapl=await fetchKlines('AAPL','US')
        if(aapl.length){
          kl=aapl
          symbol.value='AAPL'
          market.value='US'
          fallbackNotice.value='当前标的暂无真实K线，已回退到 Influx 中的 AAPL 实盘日K'
        }
      }
      if(!chart) chart=echarts.init(chartRef.value)
      const dates=kl.map(k=>k.date); const ohlc=kl.map(k=>[k.open,k.close,k.low,k.high]); const closes=kl.map(k=>Number(k.close))
      const vols=kl.map(k=>Number(k.volume||0))
      chart.setOption(applyChartTheme({
        legend:{data:['K','MA5','MA20','MA60','Vol']}, tooltip:{trigger:'axis'},
        axisPointer:{link:[{xAxisIndex:'all'}]},
        grid:[{left:50,right:20,top:40,height:'58%'},{left:50,right:20,top:'74%',height:'16%'}],
        xAxis:[
          {type:'category', data:dates, boundaryGap:true, axisLabel:{show:false}, gridIndex:0},
          {type:'category', data:dates, boundaryGap:true, gridIndex:1}
        ],
        yAxis:[
          {type:'value', scale:true, splitArea:{show:true}, gridIndex:0},
          {type:'value', scale:true, gridIndex:1, splitNumber:2}
        ],
        dataZoom:[{type:'inside', xAxisIndex:[0,1]},{type:'slider', height:18, xAxisIndex:[0,1], bottom:8}],
        series:[
          {name:'K', type:'candlestick', data:ohlc, xAxisIndex:0, yAxisIndex:0, itemStyle:{color:'#ef5350', color0:'#26a69a', borderColor:'#ef5350', borderColor0:'#26a69a'}},
          {name:'MA5', type:'line', data:ma(closes,5), xAxisIndex:0, yAxisIndex:0, showSymbol:false, smooth:true, lineStyle:{width:1}},
          {name:'MA20', type:'line', data:ma(closes,20), xAxisIndex:0, yAxisIndex:0, showSymbol:false, smooth:true, lineStyle:{width:1}},
          {name:'MA60', type:'line', data:ma(closes,60), xAxisIndex:0, yAxisIndex:0, showSymbol:false, smooth:true, lineStyle:{width:1}},
          {name:'Vol', type:'bar', data:vols, xAxisIndex:1, yAxisIndex:1, itemStyle:{color:'#64748b55'}},
        ]
      }), true)
    })
  } finally { loading.value=false }
}
onMounted(async()=>{ await loadInst(); await load(); window.addEventListener('resize',()=>chart&&chart.resize()) })
onBeforeUnmount(()=>{ chart&&chart.dispose() })
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center} .chart{height:560px;width:100%}
.mb12{margin-bottom:12px}
</style>
