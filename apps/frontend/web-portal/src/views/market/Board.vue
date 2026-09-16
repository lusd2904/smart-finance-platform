<template>
  <PageFrame
    title="行情台"
    subtitle="只读报价 · 点入 K线 / 详情"
    :loading="loading"
  >
    <template #actions>
      <el-select v-model="market" placeholder="市场" style="width:110px" @change="onMarketChange">
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

    <div v-if="featured.length" class="index-strip glass-panel">
      <span class="muted featured-label">精选 / 自选</span>
      <button
        v-for="q in featured"
        :key="`f-${q.symbol || q.name}`"
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
          <span class="muted">{{ rangeText }} · 60s REST 刷新</span>
        </div>
      </template>
      <el-table :data="paged.rows" stripe max-height="480" empty-text="暂无报价">
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
      <div class="pager">
        <span class="muted">{{ rangeText }}</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="paged.filteredTotal"
          :page-sizes="[50, 100]"
          layout="total, prev, pager, next, sizes"
        />
      </div>
    </el-card>

    <template #legend>
      <span class="legend-dots">
        <span><i class="dot-up" /> 涨红</span>
        <span><i class="dot-down" /> 跌绿</span>
      </span>
      <span>指数条 + 分页报价 · 单页最多 {{ pageSize }} 行</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Monitor, Refresh, Search } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getBoardQuotes } from '@/api/market'
import { pageBoardRows, pickBoardLists } from '@/utils/boardQuotes'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { goAiChat, goTerminal, unwrap } from '@/utils/list'
import { errorText } from '@/utils/stubs'

const loading = ref(false)
const loadError = ref('')
const market = ref('')
const keyword = ref('')
const page = ref(1)
const pageSize = ref(50)
const rows = shallowRef([])
const indices = shallowRef([])
const featured = shallowRef([])
let timer = null

const paged = computed(() => pageBoardRows(rows.value, {
  keyword: keyword.value,
  page: page.value,
  pageSize: pageSize.value
}))

const rangeText = computed(() => {
  const { filteredTotal, showingFrom, showingTo } = paged.value
  if (!filteredTotal) return '暂无报价'
  return `显示 ${showingFrom}–${showingTo} / 共 ${filteredTotal} 只`
})

watch(keyword, () => {
  page.value = 1
})

function onMarketChange() {
  page.value = 1
  load()
}

async function load(silent = false) {
  if (!silent) loading.value = true
  if (!silent) loadError.value = ''
  try {
    const boardRes = await getBoardQuotes({ market: market.value || undefined })
    const data = unwrap(boardRes)
    const picked = pickBoardLists(data)
    indices.value = picked.indices
    featured.value = picked.featured
    rows.value = picked.rows
    if (!silent && data.message && !picked.indices.length && !picked.rows.length && !picked.featured.length) {
      loadError.value = String(data.message)
    }
  } catch (e) {
    indices.value = []
    featured.value = []
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
  align-items: center;
}
.featured-label { margin-right: 4px; }
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
.pager { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-top: 10px; flex-wrap: wrap; }
</style>
