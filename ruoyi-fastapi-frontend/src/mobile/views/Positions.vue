<template>
  <div class="m-page">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <header class="m-pos-head">
        <div class="m-pos-head__row">
          <span>净资产</span>
          <div class="m-ccy">
            <button type="button" :class="{ 'is-on': display === 'HKD' }" @click="display = 'HKD'">港元</button>
            <button type="button" :class="{ 'is-on': display === 'USD' }" @click="display = 'USD'">美元</button>
          </div>
        </div>
        <div class="m-pos-head__net m-num">{{ prefix }}{{ netText }}</div>
        <div class="m-pos-head__cash">可用现金 {{ prefix }}{{ cashText }}</div>
      </header>
      <EmptyState v-if="error && !items.length" :message="error || '加载失败'" retry @retry="load" />
      <EmptyState v-else-if="!loading && !items.length" :message="emptyMsg || '暂无持仓'" retry @retry="load" />
      <Skeleton v-if="loading && !items.length" :rows="6" />
      <button
        v-for="row in items"
        :key="row.symbol"
        type="button"
        class="m-pos"
        @click="openSymbol(row)"
      >
        <div class="m-pos__top">
          <div>
            <div class="m-pos__name">{{ row.symbolName || row.symbol }}</div>
            <div class="m-pos__code">{{ row.symbol }} · {{ row.quantity ?? '--' }}股</div>
          </div>
          <div class="m-pos__right">
            <div class="m-num" :class="'m-' + changeTone(row.changePct)">{{ fmtPrice(row.last) }}</div>
            <div class="m-num" :class="'m-' + changeTone(row.changePct)">{{ fmtPct(row.changePct) }}</div>
          </div>
        </div>
        <div class="m-pos__bot">
          <span>成本 {{ fmtPrice(row.costPrice) }}</span>
          <span :class="'m-' + changeTone(row.pnl)">盈亏 {{ fmtSigned(row.pnl) }}</span>
          <button type="button" class="m-pos__trade" @click.stop="openTicket(row)">交易</button>
        </div>
      </button>
    </PullRefresh>
    <QuickOrderDrawer
      v-model="ticketOpen"
      :symbol="ticket.symbol"
      :market="ticket.market"
      :name="ticket.name"
      :last="ticket.last"
      :side="ticket.side"
      @done="load"
    />
  </div>
</template>

<script setup name="MobilePositions">
import { getTradeAccount, getTradePositions } from '@/api/trade'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import QuickOrderDrawer from '../components/QuickOrderDrawer.vue'
import { changeTone, fmtPct, fmtPrice, fmtSigned, fmtMoney } from '../utils/format'
import { unwrapData, unwrapList, num, str } from '../utils/payload'
import { inferMarket, quoteSymbol } from '../utils/ticketQty'

const FX = 7.8
const display = ref('HKD')
const account = ref({})
const items = ref([])
const error = ref('')
const emptyMsg = ref('暂无持仓')
const loading = ref(false)
const refreshing = ref(false)
const ticketOpen = ref(false)
const ticket = reactive({ symbol: '', market: 'US', name: '', last: null, side: 'buy' })

const router = useRouter()
const prefix = computed(() => (display.value === 'HKD' ? 'HK$' : 'US$'))

function convert(amount, currency) {
  const n = num(amount)
  if (n == null) return null
  const ccy = String(currency || 'USD').toUpperCase()
  if (display.value === 'HKD') {
    if (ccy === 'HKD') return n
    if (ccy === 'USD') return n * FX
    return n
  }
  if (ccy === 'USD') return n
  if (ccy === 'HKD') return n / FX
  return n
}

const netText = computed(() => {
  const acc = account.value || {}
  const bals = Array.isArray(acc.balances) ? acc.balances : []
  if (bals.length) {
    let sum = 0
    let any = false
    for (const b of bals) {
      const v = num(b.netAssets ?? b.totalCash)
      if (v == null) continue
      any = true
      sum += convert(v, b.currency) || 0
    }
    return any ? fmtMoney(sum) : '--'
  }
  const v = convert(acc.netAssets ?? acc.totalCash, acc.currency)
  return v == null ? '--' : fmtMoney(v)
})

const cashText = computed(() => {
  const acc = account.value || {}
  const bals = Array.isArray(acc.balances) ? acc.balances : []
  if (bals.length) {
    let sum = 0
    let any = false
    for (const b of bals) {
      const v = num(b.availableCash ?? b.totalCash)
      if (v == null) continue
      any = true
      sum += convert(v, b.currency) || 0
    }
    return any ? fmtMoney(sum) : '--'
  }
  const v = convert(acc.availableCash ?? acc.totalCash, acc.currency)
  return v == null ? '--' : fmtMoney(v)
})

function computeRow(p) {
  const last = num(p.last ?? p.lastDone)
  const prev = num(p.prevClose)
  const cost = num(p.costPrice)
  const qty = num(p.quantity)
  let changePct = null
  if (last != null && prev) changePct = ((last - prev) / prev) * 100
  let pnl = null
  if (last != null && cost != null && qty != null) pnl = (last - cost) * qty
  return {
    ...p,
    symbol: str(p.symbol),
    symbolName: str(p.symbolName),
    quantity: qty,
    costPrice: cost,
    last,
    changePct,
    pnl,
    market: p.market || inferMarket(p.symbol)
  }
}

function openSymbol(row) {
  router.push({
    path: `/m/symbol/${encodeURIComponent(quoteSymbol(row.symbol) || row.symbol)}`,
    query: { market: row.market || 'US' }
  })
}

function openTicket(row) {
  ticket.symbol = quoteSymbol(row.symbol) || row.symbol
  ticket.market = row.market || inferMarket(row.symbol)
  ticket.name = row.symbolName
  ticket.last = row.last
  ticket.side = 'sell'
  ticketOpen.value = true
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [accRes, posRes] = await Promise.all([
      getTradeAccount(),
      getTradePositions()
    ])
    account.value = unwrapData(accRes)
    const payload = unwrapData(posRes)
    const list = unwrapList(posRes, ['positions', 'items', 'rows'])
    items.value = list.map(computeRow)
    if (payload.configured === false) {
      emptyMsg.value = payload.message || '未配置长桥凭证'
    } else {
      emptyMsg.value = payload.message || '暂无持仓'
    }
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
  if (!items.value.length) load()
})
</script>

<style scoped lang="scss">
.m-pos-head {
  padding: 16px 16px 12px;
  background: #fff;
}
.m-pos-head__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #6b7280;
  font-size: 13px;
}
.m-ccy button {
  border: 0;
  background: transparent;
  color: #8b8d98;
  font-size: 13px;
  font-weight: 600;
  margin-left: 10px;
}
.m-ccy button.is-on { color: #111827; }
.m-pos-head__net {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 800;
}
.m-pos-head__cash {
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
}
.m-pos {
  display: block;
  width: 100%;
  padding: 12px 16px;
  border: 0;
  background: #fff;
  border-bottom: 1px solid #f0f1f3;
  text-align: left;
}
.m-pos__top {
  display: flex;
  justify-content: space-between;
}
.m-pos__name { font-weight: 800; }
.m-pos__code { color: #8b8d98; font-size: 12px; margin-top: 2px; }
.m-pos__right { text-align: right; font-weight: 700; }
.m-pos__bot {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  color: #6b7280;
  font-size: 12px;
}
.m-pos__trade {
  margin-left: auto;
  height: 26px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: #111827;
  color: #fff;
  font-size: 12px;
}
</style>
