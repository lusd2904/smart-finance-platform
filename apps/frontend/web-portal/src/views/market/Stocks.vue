<template>
  <PageFrame
    title="全部股票"
    subtitle="美股 / 港股 / A 股全市场代码 · 分页浏览 · 最新价取自本地日K"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="market" @change="onFilter">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" clearable placeholder="代码 / 名称" style="width:180px" :prefix-icon="Search" @keyup.enter="onFilter" />
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article
        v-for="card in statCards"
        :key="card.key"
        class="stat-tile glass-panel"
        :class="{ active: market === card.market }"
        @click="pick(card.market)"
      >
        <span>{{ card.label }}</span>
        <strong class="numeric">{{ card.value }}</strong>
        <small>{{ card.sub }}</small>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无标的" class="dense-table">
        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="市场" width="88">
          <template #default="{ row }">
            <span class="mkt-tag" :class="`is-${String(row.market || '').toLowerCase()}`">{{ marketLabel(row.market) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtPx(row.price ?? row.last) }}</span></template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate ?? row.changePct)">{{ fmtChange(row.changeRate ?? row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成交量" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtCompact(row.volume) }}</span></template>
        </el-table-column>
        <el-table-column label="成交额" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtCompact(row.turnover) }}</span></template>
        </el-table-column>
        <el-table-column label="" width="168" class-name="hover-acts">
          <template #default="{ row }">
            <div class="row-acts">
              <el-button link type="success" :loading="adding === row.symbol" @click.stop="addWatch(row)">加自选</el-button>
              <el-button link type="primary" @click.stop="goTerminal($router, row, { tab: 'kline' })">K线</el-button>
              <el-button link type="primary" @click.stop="goTerminal($router, row)">详情</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <span class="muted">密集表 · 最新价取自本地日K (非盘中实时)</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[50, 100]"
          layout="total, prev, pager, next, sizes"
          @current-change="load"
          @size-change="onFilter"
        />
      </div>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { addMarketWatchlist, listInstrumentUniverse } from '@/api/market'
import { changeClass, fmtChange, fmtCompact, fmtCount, fmtPx } from '@/utils/format'
import { goTerminal, marketLabel, unwrap, unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const market = ref('')
const keyword = ref('')
const list = ref([])
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const adding = ref('')
const counts = ref({ US: 0, HK: 0, CN: 0, total: 0 })

const statCards = computed(() => [
  { key: 'all', market: '', label: '合计', value: fmtCount(counts.value.total || total.value), sub: '三市场入库代码' },
  { key: 'cn', market: 'CN', label: 'A股', value: fmtCount(counts.value.CN), sub: '沪深北' },
  { key: 'hk', market: 'HK', label: '港股', value: fmtCount(counts.value.HK), sub: '港交所' },
  { key: 'us', market: 'US', label: '美股', value: fmtCount(counts.value.US), sub: 'NYSE / NASDAQ' }
])

function pick(code) {
  if (market.value === code) return
  market.value = code
  onFilter()
}
function onFilter() {
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  try {
    const res = await listInstrumentUniverse({
      market: market.value || undefined,
      keyword: keyword.value || undefined,
      pageNum: page.value,
      pageSize: pageSize.value
    })
    const data = unwrap(res)
    list.value = data.rows || unwrapList(res)
    total.value = unwrapTotal(res, list.value.length)
    if (data.counts || unwrap(res).counts) counts.value = { US: 0, HK: 0, CN: 0, total: 0, ...(data.counts || {}) }
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function addWatch(row) {
  adding.value = row.symbol
  try {
    await addMarketWatchlist({ symbol: row.symbol, market: row.market || 'US', note: '全部股票' })
    ElMessage.success('已加入自选')
  } catch (e) {
    ElMessage.error(e?.message || '加入失败')
  } finally {
    adding.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.stat-tile { cursor: pointer; }
.stat-tile.active { outline: 1px solid color-mix(in srgb, var(--accent) 40%, transparent); }
.stat-tile small { color: var(--text-secondary); font-size: 12px; }
.pager { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding-top: 10px; flex-wrap: wrap; }
.muted { color: var(--text-secondary); font-size: 12px; }
.row-acts { display: flex; opacity: 0; }
.dense-table :deep(.el-table__row:hover) .row-acts { opacity: 1; }
</style>
