<template>
  <div class="m-page">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <div class="m-chip-row">
        <button v-for="m in markets" :key="m.key" type="button" class="m-chip" :class="{ 'is-on': market === m.key }" @click="switchMarket(m.key)">{{ m.label }}</button>
      </div>
      <div v-if="tradeDate" class="m-date">{{ tradeDate }}</div>
      <EmptyState v-if="error && !items.length" :message="error || '加载失败'" retry @retry="load" />
      <EmptyState v-else-if="!loading && !items.length" :message="emptyMsg || '暂无选股单'" retry @retry="load" />
      <QuoteRow
        v-for="row in items"
        :key="row.symbol + (row.market || '')"
        :symbol="row.symbol"
        :name="row.name"
        :market="row.market"
        :last="row.last"
        :change-pct="row.changePct"
        :tag="row.recommendation"
        :tag-tone="recTone(row.recommendation)"
        :subtitle="expanded === row.symbol ? row.fullSubtitle : row.subtitle"
        @click="openSymbol(row)"
        @longpress="expanded = expanded === row.symbol ? '' : row.symbol"
      />
      <Skeleton v-if="loading && !items.length" :rows="8" />
    </PullRefresh>
  </div>
</template>

<script setup name="MobilePicks">
import { getStockPickLatest } from '@/api/market'
import PullRefresh from '../components/PullRefresh.vue'
import QuoteRow from '../components/QuoteRow.vue'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import { unwrapData, num, str } from '../utils/payload'
import { inferMarket } from '../utils/ticketQty'
import { sentimentDirection } from '../utils/riskEvents'

const markets = [
  { key: '', label: '全部' },
  { key: 'US', label: '美' },
  { key: 'HK', label: '港' },
  { key: 'CN', label: 'A' }
]

const router = useRouter()
const market = ref('')
const items = ref([])
const tradeDate = ref('')
const emptyMsg = ref('暂无选股单')
const error = ref('')
const loading = ref(false)
const refreshing = ref(false)
const expanded = ref('')

function recTone(rec) {
  return sentimentDirection(rec)
}

function switchMarket(next) {
  if (next === market.value) return
  market.value = next
  load()
}

function openSymbol(row) {
  const code = str(row.symbol)
  if (!code) return
  router.push({ path: `/m/symbol/${encodeURIComponent(code)}`, query: { market: row.market || 'US' } })
}

function formatScore(v) {
  const n = num(v)
  if (n == null) return ''
  return n <= 1 ? String(Math.round(n * 100)) : n.toFixed(0)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getStockPickLatest({ market: market.value || undefined })
    const data = unwrapData(res)
    tradeDate.value = str(data.tradeDate)
    const list = Array.isArray(data.items) ? data.items : []
    items.value = list.map((row) => {
      const parts = []
      const score = formatScore(row.pickScore)
      if (score) parts.push(score)
      if (row.stance) parts.push(row.stance)
      const summary = str(row.summary)
      const shortSum = summary.length > 18 ? summary.slice(0, 18) + '…' : summary
      if (shortSum) parts.push(shortSum)
      const full = []
      if (score) full.push(score)
      if (row.stance) full.push(row.stance)
      if (summary) full.push(summary)
      return {
        ...row,
        market: row.market || inferMarket(row.symbol, 'US'),
        last: num(row.last ?? row.price),
        changePct: num(row.changePct),
        subtitle: parts.join(' · '),
        fullSubtitle: full.join(' · ')
      }
    })
    if (data.empty === true || !items.value.length) {
      emptyMsg.value = str(data.message) || '暂无选股单'
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

<style scoped>
.m-date {
  padding: 4px 16px 0;
  color: #8b8d98;
  font-size: 12px;
}
</style>
