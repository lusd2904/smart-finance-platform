<template>
  <PageFrame
    title="行情台"
    subtitle="只读报价 · 点入 K线 / 详情"
    :loading="loading"
  >
    <template #actions>
      <el-select v-model="market" placeholder="市场" style="width:110px" @change="load">
        <el-option label="全部" value="" />
        <el-option label="美股" value="US" />
        <el-option label="港股" value="HK" />
        <el-option label="A股" value="CN" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:160px" :prefix-icon="Search" />
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      <el-button type="success" :icon="Monitor" @click="$router.push('/trade/terminal')">专业交易终端</el-button>
    </template>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>批量报价</h3>
          <span class="muted">实时最新价 · WS patch / 60s REST</span>
        </div>
      </template>
      <el-table :data="filtered" stripe empty-text="暂无数据">
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            <span class="mkt-tag" :class="`is-${String(row.market || '').toLowerCase()}`">{{ row.market }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtPx(row.price ?? row.last) }}</span></template>
        </el-table-column>
        <el-table-column label="涨跌幅%" width="120" align="right">
          <template #default="{ row }">
            <span class="quote-chg" :class="changeClass(row.changeRate ?? row.changePct ?? row.change)">
              {{ fmtChange(row.changeRate ?? row.changePct ?? row.change) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" @click="goTerminal($router, row, { tab: 'kline' })">K线</el-button>
            <el-button link type="primary" @click="goTerminal($router, row, { tab: 'detail' })">详情</el-button>
            <el-button link type="primary" @click="goAiChat($router, row)">AI研判</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <template #legend>
      <span class="legend-dots">
        <span><i class="dot-up" /> 涨红</span>
        <span><i class="dot-down" /> 跌绿</span>
      </span>
      <span>{{ themeMeta.id }} · tabular-nums · glass-panel blur 12px · 对齐现网 /market/board</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Monitor, Refresh, Search } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getBoardQuotes } from '@/api/market'
import { useTheme } from '@/composables/useTheme'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { goAiChat, goTerminal, unwrap, unwrapList } from '@/utils/list'

const { themeMeta } = useTheme()
const loading = ref(false)
const market = ref('')
const keyword = ref('')
const rows = ref([])
let timer = null

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw))
})

function isIndexRow(row) {
  const cat = String(row?.category || row?.kind || row?.type || '').toLowerCase()
  if (cat === 'index') return true
  const sym = String(row?.symbol || '')
  return sym.startsWith('^') || sym.startsWith('.')
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const boardRes = await getBoardQuotes({ market: market.value || undefined })
    const data = unwrap(boardRes)
    const list = data.rows || data.quotes || unwrapList(boardRes)
    rows.value = list.filter((r) => !isIndexRow(r))
  } catch {
    rows.value = []
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => load(true), 60000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-header h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
</style>
