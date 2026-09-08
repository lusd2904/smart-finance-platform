<template>
  <PageFrame title="资金与日历" :loading="loading">
    <template #actions>
      <el-radio-group v-model="sectorKind" @change="load">
        <el-radio-button value="industry">行业</el-radio-button>
        <el-radio-button value="concept">概念</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>交易日</span><strong>{{ board.tradeDate || '--' }}</strong></article>
      <article class="stat-tile glass-panel"><span>涨停</span><strong class="up">{{ board.limitUpCount ?? (board.limitUp || []).length }}</strong></article>
      <article class="stat-tile glass-panel"><span>龙虎榜</span><strong>{{ (board.longhu || board.dragonTiger || []).length }}</strong></article>
      <article class="stat-tile glass-panel"><span>板块</span><strong>{{ sectors.length }}</strong></article>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="glass-panel">
          <template #header><h3>板块资金净流入</h3></template>
          <el-table :data="sectors" stripe max-height="420" empty-text="暂无板块资金">
            <el-table-column prop="name" label="板块" min-width="120" />
            <el-table-column label="净流入" width="120" align="right">
              <template #default="{ row }">
                <span :class="changeClass(row.netInflow ?? row.net)">{{ fmtAmount(row.netInflow ?? row.net) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="涨跌" width="90" align="right">
              <template #default="{ row }">
                <span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="glass-panel">
          <template #header><h3>涨停池</h3></template>
          <el-table :data="board.limitUp || []" stripe max-height="420" empty-text="暂无涨停">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="name" label="名称" min-width="90" />
            <el-table-column label="涨跌" width="80" align="right">
              <template #default="{ row }">
                <span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="boards" label="连板" width="60" align="right" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>日历</h3></template>
      <el-table :data="calendar" stripe empty-text="暂无日历">
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="title" label="事件" min-width="180" />
        <el-table-column prop="kind" label="类型" width="100" />
        <el-table-column prop="market" label="市场" width="80" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getMarketFlowBoard } from '@/api/market'
import { changeClass, fmtAmount, fmtChange } from '@/utils/format'
import { unwrap } from '@/utils/list'

const loading = ref(false)
const sectorKind = ref('industry')
const board = ref({})
const sectors = ref([])
const calendar = ref([])

async function load() {
  loading.value = true
  try {
    const res = await getMarketFlowBoard({ kind: sectorKind.value })
    const data = unwrap(res)
    board.value = data
    sectors.value = data.sectors || data.industry || data.concept || []
    calendar.value = data.calendar || data.events || data.macro || []
  } catch {
    board.value = {}
    sectors.value = []
    calendar.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
</style>
