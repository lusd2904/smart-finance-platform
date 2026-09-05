<template>
  <div class="m-page m-symbol" @touchstart.passive="onSwipeStart" @touchend="onSwipeEnd">
    <header class="m-symbol__head">
      <button type="button" class="m-back" @click="goBack">‹</button>
      <div class="m-symbol__id">
        <div class="name">{{ header.name || header.symbol }}</div>
        <div class="code">{{ header.symbol }} · {{ marketLabel(market) }}</div>
      </div>
    </header>
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <EmptyState v-if="error && !header.symbol" :message="error || '加载失败'" retry @retry="load" />
      <template v-else>
        <div class="m-symbol__quote">
          <div class="last m-num" :class="'m-' + changeTone(header.changePct)">{{ fmtPrice(header.last) }}</div>
          <div class="chg m-num" :class="'m-' + changeTone(header.changePct)">{{ fmtPct(header.changePct) }}</div>
        </div>
        <MetricsGrid
          :core="coreCells"
          :extra="extraCells"
          :expanded="moreOpen"
          :show-more="extraCells.length > 0 || !snapshotLoaded"
          @toggle="toggleMore"
        />
        <div class="m-underline-tabs">
          <button
            v-for="p in periods"
            :key="p.key"
            type="button"
            :class="{ 'is-on': period === p.key }"
            @click="changePeriod(p.key)"
          >{{ p.label }}</button>
        </div>
        <EmptyState v-if="klineError" :message="klineError" retry @retry="loadKline" />
        <KlineChart v-else-if="bars.length" :bars="bars" :period="period" />
        <EmptyState v-else-if="!klineLoading" message="暂无K线" retry @retry="loadKline" />
        <Skeleton v-else :rows="4" />
      </template>
    </PullRefresh>
    <div class="m-symbol__bar">
      <button type="button" class="ghost" @click="toggleWatch">{{ watched ? '已加自选' : '加自选' }}</button>
      <button type="button" class="buy" @click="openTicket('buy')">买入</button>
      <button type="button" class="sell" @click="openTicket('sell')">卖出</button>
    </div>
    <QuickOrderDrawer
      v-model="ticketOpen"
      :symbol="code"
      :market="market"
      :name="header.name"
      :last="header.last"
      :side="ticketSide"
      @done="load"
    />
    <GroupPickSheet
      v-model="groupOpen"
      :groups="groupOptions"
      allow-skip
      hint="先选分组再加入自选；跳过则 note 为空"
      @pick="onPickGroup"
      @skip="onSkipGroup"
      @cancel="onCancelGroup"
    />
  </div>
</template>

<script setup>
import { getKline, getSymbolOverview, addMarketWatchlist, delMarketWatchlist, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import { getTradeQuoteSnapshot } from '@/api/trade'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import KlineChart from '../components/KlineChart.vue'
import QuickOrderDrawer from '../components/QuickOrderDrawer.vue'
import MetricsGrid from '../components/MetricsGrid.vue'
import GroupPickSheet from '../components/GroupPickSheet.vue'
import { changeTone, fmtPct, fmtPrice, marketLabel } from '../utils/format'
import { unwrapData, unwrapList, num, str } from '../utils/payload'
import { KLINE_PERIODS, pickKlineBars } from '../utils/kline'
import { coreMetrics, extraMetrics, lastBar, needsTurnoverFallback } from '../utils/metrics'
import { overviewGroups, idleWatchlistAdd, nextWatchlistAdd, shouldPostWatchlist, watchlistAddBody } from '../utils/watchlist'

const route = useRoute()
const router = useRouter()
const code = computed(() => decodeURIComponent(route.params.code || ''))
const market = computed(() => String(route.query.market || 'US').toUpperCase())
const periods = KLINE_PERIODS

const period = ref('intraday')
const overview = ref({})
const snapshot = ref(null)
const bars = ref([])
const watched = ref(false)
const watchId = ref(null)
const error = ref('')
const klineError = ref('')
const klineLoading = ref(false)
const refreshing = ref(false)
const ticketOpen = ref(false)
const ticketSide = ref('buy')
const moreOpen = ref(false)
const groupOpen = ref(false)
const groupOptions = ref([])
const snapshotLoaded = ref(false)
const addState = ref(idleWatchlistAdd())

const header = computed(() => {
  const ov = overview.value || {}
  const quote = ov.quote && typeof ov.quote === 'object' ? ov.quote : ov
  const snap = snapshot.value || {}
  const lastCandle = lastBar(bars.value)
  const prev = bars.value.length >= 2 ? bars.value[bars.value.length - 2] : null
  const last = num(quote.last ?? quote.price ?? quote.close ?? snap.last ?? lastCandle?.close)
  const prevClose = num(quote.prevClose ?? quote.preClose ?? snap.prevClose ?? prev?.close)
  let changePct = num(quote.changePct ?? quote.changeRate ?? snap.changeRate)
  if (changePct == null && last != null && prevClose) {
    changePct = ((last - prevClose) / prevClose) * 100
  }
  return {
    symbol: str(ov.symbol) || code.value,
    name: str(ov.name) || str(quote.name) || str(snap.name),
    last,
    changePct
  }
})

const coreCells = computed(() => coreMetrics({
  bar: lastBar(bars.value),
  overview: overview.value,
  snapshot: snapshot.value
}))

const extraCells = computed(() => extraMetrics({
  overview: overview.value,
  snapshot: snapshot.value
}))

async function loadOverview() {
  const res = await getSymbolOverview(code.value, { market: market.value })
  overview.value = unwrapData(res)
}

async function loadSnapshot() {
  try {
    const res = await getTradeQuoteSnapshot({ symbol: code.value, market: market.value })
    snapshot.value = unwrapData(res)
  } catch {
    snapshot.value = snapshot.value || {}
  } finally {
    snapshotLoaded.value = true
  }
}

async function loadKline() {
  klineError.value = ''
  klineLoading.value = true
  try {
    const res = await getKline({ symbol: code.value, market: market.value, period: period.value })
    bars.value = pickKlineBars(res)
    if (needsTurnoverFallback(coreMetrics({ bar: lastBar(bars.value), overview: overview.value, snapshot: snapshot.value }))) {
      await loadSnapshot()
    }
  } catch (e) {
    bars.value = []
    klineError.value = (e && e.message) || 'K线加载失败'
  } finally {
    klineLoading.value = false
  }
}

async function loadWatchState() {
  try {
    const res = await getMarketWatchlistOverview()
    const payload = unwrapData(res)
    groupOptions.value = overviewGroups(payload)
    const items = payload.items || []
    const hit = items.find((i) => String(i.symbol || '').toUpperCase() === code.value.toUpperCase()
      && String(i.market || '').toUpperCase() === market.value)
    if (hit) {
      watched.value = true
      watchId.value = hit.id
      return
    }
  } catch { /* list fallback */ }
  try {
    const res = await listMarketWatchlist({ pageNum: 1, pageSize: 200, symbol: code.value })
    const listed = unwrapList(res, ['rows', 'items'])
    const hit = listed.find((i) => String(i.symbol || '').toUpperCase() === code.value.toUpperCase())
    watched.value = !!hit
    watchId.value = hit?.id || null
  } catch {
    watched.value = false
  }
}

async function load() {
  error.value = ''
  try {
    await Promise.all([loadOverview(), loadKline(), loadWatchState()])
  } catch (e) {
    error.value = (e && e.message) || '加载失败'
  } finally {
    refreshing.value = false
  }
}

async function refresh() {
  refreshing.value = true
  await load()
}

async function changePeriod(next) {
  if (period.value === next) return
  period.value = next
  await loadKline()
}

async function toggleMore() {
  if (!snapshotLoaded.value) await loadSnapshot()
  if (!extraMetrics({ overview: overview.value, snapshot: snapshot.value }).length) {
    moreOpen.value = false
    return
  }
  moreOpen.value = !moreOpen.value
}

async function toggleWatch() {
  if (watched.value) {
    const prevId = watchId.value
    watched.value = false
    try {
      if (prevId) await delMarketWatchlist(prevId)
      watchId.value = null
    } catch (e) {
      watched.value = true
      watchId.value = prevId
      error.value = (e && e.message) || '自选操作失败'
    }
    return
  }
  addState.value = nextWatchlistAdd(idleWatchlistAdd(), {
    type: 'start',
    already: false,
    pending: { symbol: code.value, market: market.value }
  })
  groupOpen.value = true
}

function onPickGroup(note) {
  addState.value = nextWatchlistAdd(addState.value, { type: 'pick', note })
  commitAdd()
}

function onSkipGroup() {
  addState.value = nextWatchlistAdd(addState.value, { type: 'skip' })
  commitAdd()
}

function onCancelGroup() {
  addState.value = nextWatchlistAdd(addState.value, { type: 'cancel' })
}

async function commitAdd() {
  const state = addState.value
  if (!shouldPostWatchlist(state)) {
    addState.value = idleWatchlistAdd()
    return
  }
  const prevId = watchId.value
  watched.value = true
  try {
    await addMarketWatchlist(watchlistAddBody({
      symbol: code.value,
      market: market.value,
      note: state.note
    }))
    addState.value = idleWatchlistAdd()
    await loadWatchState()
  } catch (e) {
    addState.value = idleWatchlistAdd()
    watched.value = false
    watchId.value = prevId
    error.value = (e && e.message) || '自选操作失败'
  }
}

let swipeX = null
function onSwipeStart(e) {
  const x = e.touches && e.touches[0] ? e.touches[0].clientX : 0
  swipeX = x < 28 ? x : null
}
function onSwipeEnd(e) {
  if (swipeX == null) return
  const x = e.changedTouches && e.changedTouches[0] ? e.changedTouches[0].clientX : 0
  if (x - swipeX > 64) goBack()
  swipeX = null
}

function goBack() {
  if (typeof history !== 'undefined' && history.length > 1) router.back()
  else router.replace('/m')
}

function openTicket(side) {
  ticketSide.value = side
  ticketOpen.value = true
}

watch(() => [code.value, market.value], () => {
  period.value = period.value || 'intraday'
  snapshot.value = null
  snapshotLoaded.value = false
  moreOpen.value = false
  load()
})
onMounted(load)
</script>

<style scoped lang="scss">
.m-symbol {
  padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px));
}
.m-symbol__head {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
}
.m-back {
  width: 36px;
  height: 36px;
  border: 0;
  background: transparent;
  font-size: 26px;
  line-height: 1;
}
.m-symbol__id .name { font-weight: 800; font-size: 16px; }
.m-symbol__id .code { color: #8b8d98; font-size: 12px; }
.m-symbol__quote {
  position: sticky;
  top: 52px;
  z-index: 4;
  padding: 8px 16px 4px;
  background: #fff;
}
.m-symbol__quote .last { font-size: 32px; font-weight: 800; }
.m-symbol__quote .chg { font-size: 14px; font-weight: 700; }
.m-symbol__bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  gap: 8px;
  padding: 8px 12px calc(8px + env(safe-area-inset-bottom, 0px));
  background: #fff;
  border-top: 1px solid #ececef;
}
.m-symbol__bar button {
  flex: 1;
  height: 40px;
  border: 0;
  border-radius: 10px;
  font-weight: 700;
  color: #fff;
}
.m-symbol__bar .ghost { background: #111827; }
.m-symbol__bar .buy { background: #e5484d; }
.m-symbol__bar .sell { background: #30a46c; }
</style>
