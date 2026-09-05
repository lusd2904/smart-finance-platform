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
      <div class="m-heat-sum">
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
      <EmptyState v-if="error && !rows.length" :message="error" retry @retry="load" />
      <EmptyState v-else-if="!loading && !rows.length" :message="board === 'watch' ? '暂无自选' : '暂无热度榜'" />
      <QuoteRow
        v-for="row in rows"
        :key="(row.symbol || '') + (row.rankNo || '')"
        :symbol="row.symbol"
        :name="row.name"
        :market="row.market || market"
        :last="row.last"
        :change-pct="row.changePct ?? row.changeRate"
        :rank="board === 'top' ? row.rankNo : null"
        :in-watchlist="!!row.inWatchlist || board === 'watch'"
        @click="openSymbol(row)"
      />
      <div v-if="loading && !rows.length" class="m-empty">加载中…</div>
    </PullRefresh>
  </div>
</template>

<script setup name="MobileHeat">
import { getMarketHeatDaily, getMarketIndexQuotes, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import PullRefresh from '../components/PullRefresh.vue'
import QuoteRow from '../components/QuoteRow.vue'
import EmptyState from '../components/EmptyState.vue'
import { changeTone, fmtAmount, fmtPct, fmtTime } from '../utils/format'
import { unwrapData, unwrapList, num, str } from '../utils/payload'
import { inferMarket } from '../utils/ticketQty'

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
const indexes = ref([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')

const rows = computed(() => (board.value === 'watch' ? watchItems.value : top50.value))

function switchMarket(next) {
  if (next === market.value) return
  market.value = next
  load()
}

function openSymbol(row) {
  const code = str(row.symbol)
  if (!code) return
  const mkt = str(row.market) || market.value
  router.push({ path: `/m/symbol/${encodeURIComponent(code)}`, query: { market: mkt } })
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
    const items = payload.items || []
    if (items.length) {
      watchItems.value = items.map(normalizeWatch)
      return
    }
  } catch { /* fall through to list */ }
  try {
    const res = await listMarketWatchlist({ pageNum: 1, pageSize: 200, enabled: '1' })
    const rows = unwrapList(res, ['rows', 'items'])
    watchItems.value = rows.map(normalizeWatch)
  } catch {
    watchItems.value = []
  }
}

function normalizeWatch(row) {
  return {
    ...row,
    name: row.name || row.symbolName || row.symbol,
    market: row.market || inferMarket(row.symbol, market.value),
    last: num(row.last ?? row.price),
    changePct: num(row.changePct ?? row.changeRate),
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
  if (!top50.value.length) load()
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
.m-heat-sum {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #ececef;
}
.m-heat-sum .k {
  color: #8b8d98;
  font-size: 11px;
}
.m-heat-sum .v {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
}
</style>
