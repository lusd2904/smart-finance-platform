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
        <div v-if="ohlc" class="m-ohlc">
          <div><span>开</span><b class="m-num">{{ fmtPrice(ohlc.open) }}</b></div>
          <div><span>高</span><b class="m-num">{{ fmtPrice(ohlc.high) }}</b></div>
          <div><span>低</span><b class="m-num">{{ fmtPrice(ohlc.low) }}</b></div>
          <div><span>收</span><b class="m-num">{{ fmtPrice(ohlc.close) }}</b></div>
        </div>
        <div class="m-underline-tabs">
          <button type="button" :class="{ 'is-on': period === 'intraday' }" @click="changePeriod('intraday')">分时</button>
          <button type="button" :class="{ 'is-on': period === 'daily' }" @click="changePeriod('daily')">日K</button>
        </div>
        <KlineChart :bars="bars" :period="period" />
        <EmptyState v-if="klineError" :message="klineError" retry @retry="loadKline" />
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
  </div>
</template>

<script setup>
import { getKline, getSymbolOverview, addMarketWatchlist, delMarketWatchlist, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import KlineChart from '../components/KlineChart.vue'
import QuickOrderDrawer from '../components/QuickOrderDrawer.vue'
import { changeTone, fmtPct, fmtPrice, marketLabel } from '../utils/format'
import { unwrapData, unwrapList, num, str } from '../utils/payload'

const route = useRoute()
const router = useRouter()
const code = computed(() => decodeURIComponent(route.params.code || ''))
const market = computed(() => String(route.query.market || 'US').toUpperCase())

const period = ref('intraday')
const overview = ref({})
const bars = ref([])
const watched = ref(false)
const watchId = ref(null)
const error = ref('')
const klineError = ref('')
const refreshing = ref(false)
const ticketOpen = ref(false)
const ticketSide = ref('buy')

const header = computed(() => {
  const ov = overview.value || {}
  const quote = ov.quote && typeof ov.quote === 'object' ? ov.quote : ov
  const lastBar = bars.value[bars.value.length - 1]
  const prev = bars.value.length >= 2 ? bars.value[bars.value.length - 2] : null
  const last = num(quote.last ?? quote.price ?? quote.close ?? lastBar?.close)
  const prevClose = num(quote.prevClose ?? quote.preClose ?? prev?.close)
  let changePct = num(quote.changePct ?? quote.changeRate)
  if (changePct == null && last != null && prevClose) {
    changePct = ((last - prevClose) / prevClose) * 100
  }
  return {
    symbol: str(ov.symbol) || code.value,
    name: str(ov.name) || str(quote.name),
    last,
    changePct
  }
})

const ohlc = computed(() => {
  const last = bars.value[bars.value.length - 1]
  if (last && (last.open != null || last.high != null)) {
    return { open: last.open, high: last.high, low: last.low, close: last.close }
  }
  const ov = overview.value || {}
  const quote = ov.quote && typeof ov.quote === 'object' ? ov.quote : ov
  if (quote.open == null && quote.high == null) return null
  return { open: quote.open, high: quote.high, low: quote.low, close: quote.close ?? quote.last }
})

function pickBars(res) {
  const payload = unwrapData(res)
  return unwrapList({ data: payload }, ['klines', 'items', 'bars', 'list']).map((b) => ({
    date: str(b.date || b.time),
    open: num(b.open),
    high: num(b.high),
    low: num(b.low),
    close: num(b.close ?? b.last),
    volume: num(b.volume)
  }))
}

async function loadOverview() {
  const res = await getSymbolOverview(code.value, { market: market.value })
  overview.value = unwrapData(res)
}

async function loadKline() {
  klineError.value = ''
  try {
    const res = await getKline({ symbol: code.value, market: market.value, period: period.value })
    bars.value = pickBars(res)
  } catch (e) {
    klineError.value = (e && e.message) || 'K线加载失败'
  }
}

async function loadWatchState() {
  try {
    const res = await getMarketWatchlistOverview()
    const items = unwrapData(res).items || []
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
    const rows = unwrapList(res, ['rows', 'items'])
    const hit = rows.find((i) => String(i.symbol || '').toUpperCase() === code.value.toUpperCase())
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

async function toggleWatch() {
  const next = !watched.value
  const prevId = watchId.value
  watched.value = next
  try {
    if (!next && prevId) {
      await delMarketWatchlist(prevId)
      watchId.value = null
    } else if (next) {
      await addMarketWatchlist({ symbol: code.value, market: market.value })
      await loadWatchState()
    }
  } catch (e) {
    watched.value = !next
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

watch(() => [code.value, market.value], load)
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
.m-ohlc {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 8px 16px 12px;
  background: #fff;
  font-size: 12px;
  color: #6b7280;
}
.m-ohlc b { display: block; color: #111827; margin-top: 2px; }
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
