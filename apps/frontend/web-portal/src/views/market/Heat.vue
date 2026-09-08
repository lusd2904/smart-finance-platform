<template>
  <PageFrame title="三市场热度" :loading="loading">
    <template #actions>
      <el-radio-group v-model="market" @change="loadDaily">
        <el-radio-button value="CN">A股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
      </el-radio-group>
      <el-select v-model="tradeDate" clearable placeholder="交易日" style="width:132px" @change="loadDaily">
        <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="loadDaily">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article class="stat-tile glass-panel">
        <span>{{ heat.indexName || '指数' }}</span>
        <strong :class="changeClass(heat.indexChangePct)">{{ fmtChange(heat.indexChangePct) }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>成交额</span>
        <strong>{{ fmtAmount(heat.totalTurnover) }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>涨 / 跌</span>
        <strong><span class="up">{{ heat.advanceCount ?? '--' }}</span> / <span class="down">{{ heat.declineCount ?? '--' }}</span></strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>热度</span>
        <strong>{{ heat.heatScore ?? '--' }}</strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>成交额 Top50</h3>
          <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:180px" />
        </div>
      </template>
      <el-table :data="filteredTop" stripe empty-text="暂无 Top50">
        <el-table-column prop="rankNo" label="#" width="52" />
        <el-table-column prop="symbol" label="代码" width="112" />
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column label="市值" width="118" align="right">
          <template #default="{ row }">{{ fmtAmount(row.marketCap) }}</template>
        </el-table-column>
        <el-table-column label="成交额" width="122" align="right">
          <template #default="{ row }">{{ fmtAmount(row.turnover) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="104" align="right">
          <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span></template>
        </el-table-column>
        <el-table-column label="" width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push('/trade/terminal')">行情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getMarketHeatDaily, getMarketHeatDates } from '@/api/market'
import { changeClass, fmtAmount, fmtChange } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const market = ref('CN')
const tradeDate = ref('')
const dates = ref([])
const heat = ref({})
const top50 = ref([])
const keyword = ref('')

const filteredTop = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return top50.value
  return top50.value.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw))
})

async function loadDates() {
  try {
    const res = await getMarketHeatDates({ market: market.value })
    const list = unwrapList(res)
    dates.value = list.map((d) => (typeof d === 'string' ? d : d.tradeDate || d.date)).filter(Boolean)
  } catch {
    dates.value = []
  }
}

async function loadDaily() {
  loading.value = true
  try {
    const res = await getMarketHeatDaily({ market: market.value, tradeDate: tradeDate.value || undefined })
    const data = unwrap(res)
    heat.value = data.heat || data.snapshot || data
    top50.value = data.top50 || data.items || []
    if (!tradeDate.value && (heat.value.tradeDate || data.tradeDate)) {
      tradeDate.value = heat.value.tradeDate || data.tradeDate
    }
  } catch {
    heat.value = {}
    top50.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadDates()
  await loadDaily()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-header h3 { margin: 0; font-size: 15px; }
</style>
