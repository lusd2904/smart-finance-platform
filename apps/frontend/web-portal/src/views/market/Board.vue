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

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <div v-if="indices.length" class="index-strip glass-panel">
      <button
        v-for="q in indices"
        :key="q.symbol || q.name"
        type="button"
        class="index-item"
        @click="goTerminal($router, q, { tab: 'kline' })"
      >
        <span class="mkt-tag">{{ q.market }}</span>
        <span>{{ q.name || q.symbol }}</span>
        <strong class="numeric">{{ fmtPx(q.price ?? q.last) }}</strong>
        <em :class="changeClass(q.changeRate ?? q.changePct ?? q.change)">{{ fmtChange(q.changeRate ?? q.changePct ?? q.change) }}</em>
      </button>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-header">
          <h3>批量报价</h3>
          <span class="muted">实时最新价 · 60s REST 刷新</span>
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
      <span>{{ themeMeta.id }} · tabular-nums · glass-panel blur 12px · 60s REST · 对齐现网 /market/board</span>
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
import { errorText } from '@/utils/stubs'

const { themeMeta } = useTheme()
const loading = ref(false)
const loadError = ref('')
const market = ref('')
const keyword = ref('')
const rows = ref([])
const indices = ref([])
let timer = null

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw))
})

async function load(silent = false) {
  if (!silent) loading.value = true
  if (!silent) loadError.value = ''
  try {
    const boardRes = await getBoardQuotes({ market: market.value || undefined })
    const data = unwrap(boardRes)
    const indexRows = Array.isArray(data.indices) ? data.indices : []
    const list = data.rows || data.quotes || unwrapList(boardRes)
    const quoteRows = Array.isArray(list) ? list : []
    indices.value = indexRows
    rows.value = quoteRows
    if (!silent && data.message && !indices.value.length && !rows.value.length) loadError.value = String(data.message)
  } catch (e) {
    indices.value = []
    rows.value = []
    loadError.value = errorText(e, '行情台加载失败')
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
.index-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.index-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  border: 0;
  border-radius: 9px;
  background: var(--surface-muted);
  color: inherit;
  cursor: pointer;
}
.index-item em { font-style: normal; font-variant-numeric: tabular-nums; }
</style>
