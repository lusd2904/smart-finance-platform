<template>
  <PageFrame
    title="资金与日历"
    subtitle="A 股板块资金 / 涨停 / 龙虎榜 · 宏观与美股财报日历"
    badge="「资金与日历 /market/flow」"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="sectorKind" @change="load">
        <el-radio-button value="industry">行业</el-radio-button>
        <el-radio-button value="concept">概念</el-radio-button>
      </el-radio-group>
      <el-tag effect="plain" size="small">交易日 {{ board.tradeDate || '--' }}</el-tag>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article v-for="card in statCards" :key="card.label" class="stat-tile glass-panel">
        <span>{{ card.label }}</span>
        <strong :class="card.tone">{{ card.value }}</strong>
      </article>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>板块资金净流入</h3>
              <span class="muted">面积越大净流入越大 · 红流入绿流出</span>
            </div>
          </template>
          <div ref="treeRef" class="tree-chart" />
          <el-empty v-if="!sectors.length && !loading" description="暂无板块资金" :image-size="64" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>涨停池</h3>
              <span class="muted">{{ board.limitUpCount || (board.limitUp || []).length || 0 }} 只</span>
            </div>
          </template>
          <el-table :data="board.limitUp || []" stripe max-height="360" empty-text="暂无涨停" @row-click="openCn">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="90" />
            <el-table-column prop="industry" label="行业" min-width="80" />
            <el-table-column label="涨跌" width="80" align="right">
              <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span></template>
            </el-table-column>
            <el-table-column prop="boards" label="连板" width="60" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="glass-panel">
          <template #header><h3>龙虎榜净买</h3></template>
          <el-table :data="board.lhb || board.longhu || board.dragonTiger || []" stripe max-height="320" empty-text="暂无龙虎榜" @row-click="openCn">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="90" />
            <el-table-column label="涨跌" width="80" align="right">
              <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span></template>
            </el-table-column>
            <el-table-column label="净买额" width="110" align="right">
              <template #default="{ row }">{{ fmtAmount(row.netAmt ?? row.net) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>宏观日历</h3>
              <span class="muted">{{ calendar.date || '--' }} Nasdaq</span>
            </div>
          </template>
          <el-table :data="calendar.macro || []" stripe max-height="200" empty-text="暂无宏观">
            <el-table-column prop="time" label="时间" width="80" />
            <el-table-column prop="country" label="国家" width="90" />
            <el-table-column prop="title" label="事件" min-width="140" show-overflow-tooltip />
            <el-table-column prop="actual" label="公布" width="80" />
            <el-table-column prop="consensus" label="预期" width="80" />
          </el-table>
          <h4 class="sub-title">美股财报</h4>
          <el-table :data="calendar.earnings || []" stripe max-height="160" empty-text="暂无财报" @row-click="openUs">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="120" />
            <el-table-column prop="time" label="时段" width="110" />
            <el-table-column prop="epsForecast" label="EPS预期" width="90" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import PageFrame from '@/components/page/PageFrame.vue'
import { getMarketFlowBoard } from '@/api/market'
import { changeClass, fmtAmount, fmtChange } from '@/utils/format'
import { goTerminal, unwrap } from '@/utils/list'

const router = useRouter()
const loading = ref(false)
const sectorKind = ref('industry')
const board = ref({})
const treeRef = ref()
let chart

const sectors = computed(() => {
  if (sectorKind.value === 'concept') return board.value.concept || board.value.sectors || []
  return board.value.sectors || board.value.industry || []
})
const calendar = computed(() => board.value.calendar || {})
const statCards = computed(() => {
  const list = sectors.value
  const net = list.reduce((s, r) => s + (Number(r.netInflow ?? r.net) || 0), 0)
  const up = list.filter((r) => Number(r.changePct) > 0).length
  return [
    { label: '交易日', value: board.value.tradeDate || '--', tone: '' },
    { label: '涨停家数', value: board.value.limitUpCount ?? (board.value.limitUp || []).length, tone: 'up' },
    { label: '板块净流入', value: fmtAmount(net), tone: net >= 0 ? 'up' : 'down' },
    { label: '上涨板块', value: `${up}/${list.length || 0}`, tone: '' }
  ]
})

function openCn(row) {
  goTerminal(router, { ...row, market: 'CN' })
}
function openUs(row) {
  goTerminal(router, { ...row, market: 'US' })
}

function renderTree() {
  if (!treeRef.value) return
  if (!chart) chart = echarts.init(treeRef.value)
  const data = sectors.value.map((r) => ({
    name: r.name,
    value: Math.abs(Number(r.netInflow ?? r.net) || 0),
    changePct: r.changePct,
    netInflow: r.netInflow ?? r.net,
    itemStyle: {
      color: Number(r.netInflow ?? r.net) >= 0
        ? getComputedStyle(document.documentElement).getPropertyValue('--stat-up').trim() || '#f87171'
        : getComputedStyle(document.documentElement).getPropertyValue('--stat-down').trim() || '#34d399'
    }
  }))
  chart.setOption({
    tooltip: {
      formatter: (p) => {
        const d = p.data || {}
        return `${p.name}<br/>净流入 ${fmtAmount(d.netInflow)}<br/>涨跌 ${fmtChange(d.changePct)}`
      }
    },
    series: [{ type: 'treemap', roam: false, breadcrumb: { show: false }, data, nodeClick: false, width: '100%', height: '100%' }]
  }, true)
}

async function load() {
  loading.value = true
  try {
    const res = await getMarketFlowBoard({ sectorKind: sectorKind.value, kind: sectorKind.value, limit: 20 })
    board.value = unwrap(res)
    await nextTick()
    renderTree()
  } catch {
    board.value = {}
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', () => chart && chart.resize())
})
onBeforeUnmount(() => {
  chart && chart.dispose()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-header h3, h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.tree-chart { height: 360px; width: 100%; }
.sub-title { margin: 12px 0 8px; font-size: 13px; color: var(--text-emphasis); }
</style>
