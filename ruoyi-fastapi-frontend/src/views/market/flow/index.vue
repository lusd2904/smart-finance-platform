<template>
  <div class="app-container flow-page">
    <div class="page-hero">
      <div>
        <h2>资金与日历</h2>
        <p>A 股板块资金 / 涨停 / 龙虎榜（东财）· 宏观与美股财报日历（Nasdaq）</p>
      </div>
      <div class="acts">
        <el-radio-group v-model="sectorKind" size="small" @change="load">
          <el-radio-button label="industry">行业</el-radio-button>
          <el-radio-button label="concept">概念</el-radio-button>
        </el-radio-group>
        <el-tag v-if="board.tradeDate" size="small" effect="plain">交易日 {{ board.tradeDate }}</el-tag>
        <el-button type="primary" icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="mb16">
      <el-col :xs="12" :sm="6" v-for="card in statCards" :key="card.label">
        <div class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.tone">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">板块资金净流入</span>
              <span class="panel-sub">面积越大净流入越大</span>
            </div>
          </template>
          <div ref="treeRef" class="tree-chart" />
          <el-empty v-if="!sectors.length && !loading" description="暂无板块资金数据" :image-size="64" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">涨停池</span>
              <span class="panel-sub">{{ board.limitUpCount || 0 }} 只</span>
            </div>
          </template>
          <el-table :data="board.limitUp || []" size="small" max-height="360" @row-click="openCn">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="90" show-overflow-tooltip />
            <el-table-column prop="changePct" label="涨跌" width="80" align="right">
              <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtPct(row.changePct) }}</span></template>
            </el-table-column>
            <el-table-column prop="boards" label="连板" width="60" align="right" />
            <el-table-column prop="industry" label="行业" min-width="80" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">龙虎榜净买</span>
              <span class="panel-sub">营业部席位</span>
            </div>
          </template>
          <el-table :data="board.lhb || []" size="small" max-height="360" @row-click="openCn">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="90" show-overflow-tooltip />
            <el-table-column prop="changePct" label="涨跌" width="80" align="right">
              <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtPct(row.changePct) }}</span></template>
            </el-table-column>
            <el-table-column label="净买额" width="110" align="right">
              <template #default="{ row }">{{ fmtAmount(row.netAmt) }}</template>
            </el-table-column>
            <el-table-column prop="explain" label="说明" min-width="140" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="mb16" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">宏观日历</span>
              <span class="panel-sub">{{ calendar.date || '--' }} Nasdaq</span>
            </div>
          </template>
          <el-table :data="calendar.macro || []" size="small" max-height="200">
            <el-table-column prop="time" label="时间" width="80" />
            <el-table-column prop="country" label="国家" width="90" show-overflow-tooltip />
            <el-table-column prop="title" label="事件" min-width="140" show-overflow-tooltip />
            <el-table-column prop="actual" label="公布" width="80" />
            <el-table-column prop="consensus" label="预期" width="80" />
          </el-table>
          <div class="sub-title">美股财报</div>
          <el-table :data="calendar.earnings || []" size="small" max-height="160" @row-click="openUs">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
            <el-table-column prop="time" label="时段" width="110" show-overflow-tooltip />
            <el-table-column prop="epsForecast" label="EPS预期" width="90" />
          </el-table>
          <el-empty v-if="!(calendar.macro || []).length && !(calendar.earnings || []).length && !loading" description="暂无日历" :image-size="56" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="MarketFlowBoard">
import echarts from '@/utils/echarts'
import { getMarketFlowBoard } from '@/api/market'
import { applyChartTheme } from '@/utils/echartsTheme'
import { changeClass, fmtAmount, fmtPct } from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const sectorKind = ref('industry')
const board = ref({ industry: [], concept: [], limitUp: [], lhb: [], calendar: {} })
const treeRef = ref()
let chart

const sectors = computed(() => board.value.sectors || board.value.industry || [])
const calendar = computed(() => board.value.calendar || {})

const statCards = computed(() => {
  const list = sectors.value
  const net = list.reduce((s, r) => s + (Number(r.netInflow) || 0), 0)
  const up = list.filter((r) => Number(r.changePct) > 0).length
  return [
    { label: '交易日', value: board.value.tradeDate || '--', tone: '' },
    { label: '涨停家数', value: board.value.limitUpCount ?? (board.value.limitUp || []).length, tone: 'up' },
    { label: '板块净流入', value: fmtAmount(net), tone: net >= 0 ? 'up' : 'down' },
    { label: '上涨板块', value: `${up}/${list.length || 0}`, tone: '' }
  ]
})

function openCn(row) {
  if (!row?.symbol) return
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: 'CN' } })
}
function openUs(row) {
  if (!row?.symbol) return
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: 'US' } })
}

function renderTree() {
  if (!treeRef.value) return
  if (!chart) chart = echarts.init(treeRef.value)
  const data = sectors.value.map((r) => ({
    name: r.name,
    value: Math.abs(Number(r.netInflow) || 0),
    changePct: r.changePct,
    netInflow: r.netInflow,
    itemStyle: { color: Number(r.netInflow) >= 0 ? '#ef5350aa' : '#26a69aaa' }
  }))
  chart.setOption(applyChartTheme({
    tooltip: {
      formatter: (p) => {
        const d = p.data || {}
        return `${p.name}<br/>净流入 ${fmtAmount(d.netInflow)}<br/>涨跌 ${fmtPct(d.changePct)}`
      }
    },
    series: [{ type: 'treemap', roam: false, breadcrumb: { show: false }, data, nodeClick: false, width: '100%', height: '100%' }]
  }), true)
}

async function load() {
  loading.value = true
  try {
    const res = await getMarketFlowBoard({ sectorKind: sectorKind.value, limit: 20 })
    board.value = res.data || {}
    await nextTick()
    renderTree()
  } catch {
    board.value = { industry: [], concept: [], limitUp: [], lhb: [], calendar: {} }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', () => chart && chart.resize())
})
onBeforeUnmount(() => { chart && chart.dispose() })
</script>

<style scoped lang="scss">
.page-hero { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.page-hero h2 { margin: 0 0 4px; color: var(--text-emphasis); }
.page-hero p { margin: 0; color: var(--text-muted); font-size: 13px; }
.acts { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.mb16 { margin-bottom: 16px; }
.stat-card {
  background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px; padding: 12px 14px; margin-bottom: 12px;
}
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-value { margin-top: 4px; font-size: 18px; font-weight: 600; color: var(--text-emphasis); font-variant-numeric: tabular-nums; }
.stat-value.up { color: var(--mc-up, #ef5350); }
.stat-value.down { color: var(--mc-down, #26a69a); }
.panel-header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.panel-title { font-weight: 600; }
.panel-sub { font-size: 12px; color: var(--text-muted); }
.tree-chart { height: 360px; width: 100%; }
.sub-title { margin: 12px 0 8px; font-size: 13px; font-weight: 600; color: var(--text-emphasis); }
.up { color: var(--mc-up, #ef5350); font-weight: 600; }
.down { color: var(--mc-down, #26a69a); font-weight: 600; }
</style>
