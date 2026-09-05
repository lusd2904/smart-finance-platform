<template>
  <div class="m-page">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <div class="m-underline-tabs">
        <button v-for="m in markets" :key="m.key" type="button" :class="{ 'is-on': market === m.key }" @click="switchMarket(m.key)">{{ m.label }}</button>
      </div>
      <div v-if="indexes.length" class="m-strip">
        <div v-for="q in indexes" :key="q.symbol || q.indexName" class="m-strip__item">
          <div class="m-strip__name">{{ q.indexName || q.name }}</div>
          <div class="m-num" :class="'m-' + changeTone(q.indexChangePct ?? q.changePct)">{{ fmtPct(q.indexChangePct ?? q.changePct) }}</div>
        </div>
      </div>
      <div v-if="board === 'top'" class="m-heat-sum">
        <div>
          <div class="k">热度</div>
          <div class="v m-num">{{ heat.heatScore != null ? heat.heatScore : '--' }}</div>
        </div>
        <div>
          <div class="k">涨 / 跌</div>
          <div class="v m-num"><span class="m-up">{{ heat.advanceCount ?? '--' }}</span> / <span class="m-down">{{ heat.declineCount ?? '--' }}</span></div>
        </div>
        <div>
          <div class="k">成交额</div>
          <div class="v m-num">{{ fmtAmount(heat.totalTurnover) }}</div>
        </div>
        <div>
          <div class="k">截止</div>
          <div class="v">{{ fmtTime(heat.asOfTime) || '--' }}</div>
        </div>
      </div>
      <div class="m-underline-tabs">
        <button type="button" :class="{ 'is-on': board === 'top' }" @click="board = 'top'">Top</button>
        <button type="button" :class="{ 'is-on': board === 'watch' }" @click="board = 'watch'">自选</button>
      </div>

      <template v-if="board === 'watch'">
        <div class="m-watch-head">
          <div class="m-watch-stats">
            <div>
              <div class="k">自选</div>
              <div class="v m-num">{{ stats.count }}</div>
            </div>
            <div>
              <div class="k">偏多</div>
              <div class="v m-num m-up">{{ stats.bullish }}</div>
            </div>
            <div>
              <div class="k">偏空</div>
              <div class="v m-num m-down">{{ stats.bearish }}</div>
            </div>
            <div>
              <div class="k">中性</div>
              <div class="v m-num m-flat">{{ stats.neutral }}</div>
            </div>
          </div>
          <div class="m-watch-tools">
            <button type="button" class="m-watch-manage" @click="searchOpen = true">管理</button>
            <button type="button" class="m-watch-search" aria-label="搜索加自选" @click="searchOpen = true">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="6.5"/><path d="M16.5 16.5L21 21"/></svg>
            </button>
          </div>
        </div>
        <div class="m-chip-row">
          <button type="button" class="m-chip" :class="{ 'is-on': !activeGroup }" @click="activeGroup = ''">全部</button>
          <button
            v-for="g in groups"
            :key="g.name"
            type="button"
            class="m-chip"
            :class="{ 'is-on': activeGroup === g.name }"
            @click="activeGroup = g.name"
          >{{ g.name }} {{ g.count }}</button>
        </div>
      </template>

      <EmptyState v-if="error && !rows.length" :message="error || '加载失败'" retry @retry="load" />
      <EmptyState v-else-if="!loading && board === 'watch' && !watchItems.length" message="暂无自选">
        <button type="button" class="m-retry" @click="searchOpen = true">去搜索加自选</button>
      </EmptyState>
      <EmptyState v-else-if="!loading && board === 'watch' && !rows.length" message="该分组暂无标的" />
      <EmptyState v-else-if="!loading && board === 'top' && !rows.length" message="暂无热度榜" retry @retry="load" />

      <template v-if="board === 'watch'">
        <SwipeQuoteRow
          v-for="row in rows"
          :key="row.id || ((row.symbol || '') + (row.market || ''))"
          :symbol="row.symbol"
          :name="row.name"
          :market="row.market || market"
          :last="row.last"
          :change-pct="row.changePct ?? row.changeRate"
          :in-watchlist="true"
          @click="openSymbol(row)"
          @delete="askDelete(row)"
        />
      </template>
      <QuoteRow
        v-else
        v-for="row in rows"
        :key="(row.symbol || '') + (row.rankNo || '')"
        :symbol="row.symbol"
        :name="row.name"
        :market="row.market || market"
        :last="row.last"
        :change-pct="row.changePct ?? row.changeRate"
        :rank="row.rankNo"
        :in-watchlist="!!row.inWatchlist"
        @click="openSymbol(row)"
        @longpress="toggleWatch(row)"
      />
      <Skeleton v-if="loading && !rows.length" :rows="8" />
    </PullRefresh>
    <WatchSearchSheet
      v-model="searchOpen"
      :groups="groups"
      :watch-items="watchItems"
      @added="loadWatch"
      @open="openSymbol"
    />
    <ConfirmSheet
      v-model="confirmOpen"
      :message="confirmMsg"
      confirm-text="删除"
      @confirm="doDelete"
      @cancel="pendingDelete = null"
    />
  </div>
</template>

<script setup name="MobileHeat">
import { getMarketHeatDaily, getMarketIndexQuotes, getMarketWatchlistOverview, listMarketWatchlist, addMarketWatchlist, delMarketWatchlist } from '@/api/market'
import PullRefresh from '../components/PullRefresh.vue'
import QuoteRow from '../components/QuoteRow.vue'
import SwipeQuoteRow from '../components/SwipeQuoteRow.vue'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import WatchSearchSheet from '../components/WatchSearchSheet.vue'
import ConfirmSheet from '../components/ConfirmSheet.vue'
import { changeTone, fmtAmount, fmtPct, fmtTime } from '../utils/format'
import { unwrapData, unwrapList, num, str } from '../utils/payload'
import { inferMarket } from '../utils/ticketQty'
import { filterItemsByGroup, itemGroups, overviewGroups, overviewStats, sameWatch, watchIdsParam } from '../utils/watchlist'

const markets = [
  { key: 'US', label: '美股' },
  { key: 'HK', label: '港股' },
  { key: 'CN', label: 'A股' }
]

const router = useRouter()
const market = ref('US')
const board = ref('top')
const heat = ref({})
const top50 = ref([])
const watchItems = ref([])
const watchOverview = ref({})
const activeGroup = ref('')
const indexes = ref([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const searchOpen = ref(false)
const confirmOpen = ref(false)
const confirmMsg = ref('')
const pendingDelete = ref(null)

const stats = computed(() => overviewStats(watchOverview.value))
const groups = computed(() => overviewGroups(watchOverview.value))
const rows = computed(() => {
  if (board.value !== 'watch') return top50.value
  return filterItemsByGroup(watchItems.value, activeGroup.value)
})

function switchMarket(next) {
  if (next === market.value) return
  market.value = next
  load()
}

function openSymbol(row) {
  const code = str(row.symbol)
  if (!code) return
  const mkt = str(row.market) || market.value
  searchOpen.value = false
  router.push({ path: `/m/symbol/${encodeURIComponent(code)}`, query: { market: mkt } })
}

function askDelete(row) {
  pendingDelete.value = row
  confirmMsg.value = `确认将 ${row.symbol || ''} 移出自选？`
  confirmOpen.value = true
}

async function doDelete() {
  const row = pendingDelete.value
  pendingDelete.value = null
  if (!row) return
  const id = watchIdsParam(row.id)
  if (!id) return
  const prev = watchItems.value.slice()
  watchItems.value = prev.filter((r) => r !== row && r.id !== row.id)
  try {
    await delMarketWatchlist(id)
    await loadWatch()
  } catch (e) {
    watchItems.value = prev
    error.value = (e && e.message) || '删除失败'
  }
}

async function toggleWatch(row) {
  try {
    const match = (w) => sameWatch(w, { symbol: row.symbol, market: row.market || market.value })
    const id = row.id || watchItems.value.find(match)?.id
    if (row.inWatchlist || board.value === 'watch') {
      if (id) await delMarketWatchlist(id)
      row.inWatchlist = false
      watchItems.value = watchItems.value.filter((r) => !match(r))
      await loadWatch()
    } else {
      await addMarketWatchlist({ symbol: row.symbol, market: row.market || market.value })
      row.inWatchlist = true
      await loadWatch()
    }
  } catch (e) {
    error.value = (e && e.message) || '自选操作失败'
  }
}

async function loadIndexes() {
  try {
    const res = await getMarketIndexQuotes()
    const items = unwrapList(res, ['items', 'data'])
    const m = market.value.toUpperCase()
    const matched = items.filter((q) => String(q.market || '').toUpperCase() === m)
    indexes.value = (matched.length ? matched : items).map((q) => ({
      ...q,
      indexName: q.indexName || q.name || q.symbol,
      indexChangePct: num(q.indexChangePct ?? q.changePct)
    }))
  } catch {
    indexes.value = []
  }
}

async function loadHeat() {
  const res = await getMarketHeatDaily({ market: market.value })
  const payload = unwrapData(res)
  heat.value = payload.heat || {}
  top50.value = (payload.top50 || []).map((r) => ({
    ...r,
    market: r.market || market.value,
    last: num(r.last ?? r.price ?? r.close),
    changePct: num(r.changePct ?? r.changeRate),
    inWatchlist: !!r.inWatchlist
  }))
}

async function loadWatch() {
  try {
    const res = await getMarketWatchlistOverview()
    const payload = unwrapData(res)
    watchOverview.value = payload
    const items = payload.items || []
    if (items.length || payload.count != null) {
      watchItems.value = items.map(normalizeWatch)
      if (activeGroup.value && !groups.value.some((g) => g.name === activeGroup.value)) {
        activeGroup.value = ''
      }
      return
    }
  } catch { /* fall through to list */ }
  try {
    const res = await listMarketWatchlist({ pageNum: 1, pageSize: 200, enabled: '1' })
    const listed = unwrapList(res, ['rows', 'items'])
    watchItems.value = listed.map(normalizeWatch)
    watchOverview.value = { items: watchItems.value, count: watchItems.value.length, groups: [] }
  } catch {
    watchItems.value = []
    watchOverview.value = {}
  }
}

function normalizeWatch(row) {
  return {
    ...row,
    name: row.name || row.symbolName || row.symbol,
    market: row.market || inferMarket(row.symbol, market.value),
    last: num(row.last ?? row.price),
    changePct: num(row.changePct ?? row.changeRate),
    changeRate: num(row.changeRate ?? row.changePct),
    groups: itemGroups(row),
    inWatchlist: true
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadIndexes(), loadHeat(), loadWatch()])
  } catch (e) {
    error.value = (e && e.message) || '加载失败，请重试'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function refresh() {
  refreshing.value = true
  await load()
}

onMounted(load)
onActivated(() => {
  if (board.value === 'watch') loadWatch()
  else if (!top50.value.length) load()
})
</script>

<style scoped lang="scss">
.m-strip {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  background: #fff;
  border-bottom: 1px solid #ececef;
}
.m-strip__item {
  flex: 1;
  min-width: 88px;
  text-align: center;
}
.m-strip__name {
  color: #6b7280;
  font-size: 11px;
  margin-bottom: 2px;
}
.m-heat-sum,
.m-watch-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  padding: 10px 12px;
  background: #fff;
}
.m-heat-sum {
  border-bottom: 1px solid #ececef;
}
.m-heat-sum .k,
.m-watch-stats .k {
  color: #8b8d98;
  font-size: 11px;
}
.m-heat-sum .v,
.m-watch-stats .v {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
}
.m-watch-head {
  display: flex;
  align-items: stretch;
  background: #fff;
  border-bottom: 1px solid #ececef;
}
.m-watch-stats {
  flex: 1;
  min-width: 0;
}
.m-watch-tools {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-right: 8px;
}
.m-watch-manage,
.m-watch-search {
  border: 0;
  background: transparent;
  color: #111827;
  font-size: 13px;
  font-weight: 700;
}
.m-watch-search {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}
@media (max-width: 360px) {
  .m-watch-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
