<template>
  <div class="m-page">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <h2 class="m-page-title">舆情</h2>
      <Skeleton v-if="loading && !analysis && !briefings.length" :rows="6" />
      <EmptyState v-else-if="error && !analysis && !briefings.length" :message="error || '加载失败'" retry @retry="load" />
      <template v-else>
        <section class="m-card">
          <div class="m-card__h">市场研判</div>
          <p class="m-summary" :class="{ 'is-open': sumOpen }">{{ analysis?.summary || '暂无摘要' }}</p>
          <button v-if="analysis?.summary" type="button" class="m-more" @click="sumOpen = !sumOpen">{{ sumOpen ? '收起' : '展开' }}</button>
          <div class="m-mkts">
            <div v-for="m in marketCards" :key="m.key" class="m-mkt">
              <div class="m-mkt__name">{{ m.label }}</div>
              <div class="m-mkt__dir" :class="'m-' + m.tone">{{ m.dirLabel }}</div>
              <div class="m-mkt__score m-num">{{ m.score == null ? '--' : Math.round(m.score) }}</div>
            </div>
          </div>
          <div v-if="riskEvents.length" class="m-risk">
            <div class="m-card__h">风险事件</div>
            <ul>
              <li v-for="(ev, i) in shownRisks" :key="i">{{ ev }}</li>
            </ul>
            <button v-if="riskEvents.length > 2 && !riskOpen" type="button" class="m-more" @click="riskOpen = true">更多</button>
          </div>
        </section>
        <section>
          <div class="m-sec-title">简报</div>
          <EmptyState v-if="!briefings.length && !loading" message="暂无简报" />
          <article v-for="item in briefings" :key="item.id || item.headline" class="m-brief">
            <h3>{{ item.headline }}</h3>
            <p class="m-brief__sum" :class="{ 'is-open': openedBrief === item.id }">{{ item.summary }}</p>
            <button v-if="item.summary" type="button" class="m-more" @click="openedBrief = openedBrief === item.id ? null : item.id">
              {{ openedBrief === item.id ? '收起' : '展开' }}
            </button>
            <div v-if="item.tickers.length" class="m-brief__syms">
              <button
                v-for="t in item.tickers"
                :key="t.symbol + t.market"
                type="button"
                class="m-chip"
                @click="openSymbol(t.symbol, t.market)"
              >{{ t.symbol }}</button>
            </div>
            <div class="m-brief__meta">
              <span>{{ item.sourceName || '—' }}</span>
              <span>{{ fmtTime(item.generatedAt) }}</span>
            </div>
          </article>
        </section>
      </template>
    </PullRefresh>
  </div>
</template>

<script setup name="MobileSentiment">
import { listAnalysis } from '@/api/sentiment'
import { getFinanceBriefings } from '@/api/market'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import { fmtTime } from '../utils/format'
import { unwrapData, unwrapRows, str } from '../utils/payload'
import { parseRiskEvents, sentimentDirection, sentimentIndexTo100 } from '../utils/riskEvents'
import { inferMarket } from '../utils/ticketQty'

const analysis = ref(null)
const briefings = ref([])
const error = ref('')
const loading = ref(false)
const refreshing = ref(false)
const sumOpen = ref(false)
const riskOpen = ref(false)
const openedBrief = ref(null)
const router = useRouter()

const DIR_LABEL = { up: '利多', down: '利空', flat: '中性', unknown: '—' }

const riskEvents = computed(() => parseRiskEvents(analysis.value?.riskEvents))
const shownRisks = computed(() => (riskOpen.value ? riskEvents.value : riskEvents.value.slice(0, 2)))

const marketCards = computed(() => {
  const a = analysis.value || {}
  return [
    { key: 'us', label: '美股', raw: a.usDirection, score: sentimentIndexTo100(a.usScore) },
    { key: 'hk', label: '港股', raw: a.hkDirection, score: sentimentIndexTo100(a.hkScore) },
    { key: 'a', label: 'A股', raw: a.aDirection, score: sentimentIndexTo100(a.aScore) }
  ].map((m) => {
    const tone = sentimentDirection(m.raw)
    return { ...m, tone, dirLabel: DIR_LABEL[tone] || m.raw || '—' }
  })
})

async function loadAnalysis() {
  const res = await listAnalysis({ pageNum: 1, pageSize: 1 })
  const rows = unwrapRows(res)
  analysis.value = rows[0] || null
}

function briefingTickers(it) {
  const fallback = str(it.market)
  const seen = new Set()
  const out = []
  const push = (code, market) => {
    const symbol = str(code)
    if (!symbol) return
    const key = symbol.toUpperCase()
    if (seen.has(key)) return
    seen.add(key)
    out.push({ symbol, market: str(market) || inferMarket(symbol, fallback || 'US') })
  }
  const list = it.symbols || []
  if (Array.isArray(list)) {
    for (const s of list) {
      if (typeof s === 'string') push(s, it.market)
      else if (s && s.symbol) push(s.symbol, s.market || it.market)
    }
  }
  if (it.payload && it.payload.symbol) push(it.payload.symbol, it.payload.market || it.market)
  return out
}

function openSymbol(code, market) {
  const symbol = str(code)
  if (!symbol) return
  router.push({
    path: `/m/symbol/${encodeURIComponent(symbol)}`,
    query: { market: market || inferMarket(symbol, 'US') }
  })
}

async function loadBriefings() {
  const res = await getFinanceBriefings({ limit: 40 })
  const payload = unwrapData(res)
  const items = payload.data || payload.items || []
  briefings.value = items.map((it) => ({
    id: it.id,
    headline: it.headline,
    summary: it.summary,
    sourceName: it.sourceName,
    generatedAt: it.generatedAt,
    tickers: briefingTickers(it)
  }))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadAnalysis(), loadBriefings()])
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
  if (!analysis.value && !briefings.value.length) load()
})
</script>

<style scoped lang="scss">
.m-page-title {
  margin: 0;
  padding: 16px 16px 0;
  font-size: 22px;
}
.m-card__h {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
}
.m-summary {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.55;
  color: #374151;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.m-summary.is-open {
  display: block;
  -webkit-line-clamp: unset;
}
.m-more {
  border: 0;
  background: transparent;
  color: #409eff;
  font-size: 12px;
  padding: 0;
}
.m-mkts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 10px;
}
.m-mkt {
  text-align: center;
  padding: 8px 4px;
  background: #f8f9fb;
  border-radius: 8px;
}
.m-mkt__name { font-size: 12px; color: #6b7280; }
.m-mkt__dir { font-size: 14px; font-weight: 800; margin: 4px 0; }
.m-mkt__score { font-size: 18px; font-weight: 800; }
.m-risk ul {
  margin: 0;
  padding-left: 18px;
  color: #6b7280;
  font-size: 13px;
}
.m-risk { margin-top: 12px; }
.m-sec-title {
  padding: 8px 16px 0;
  font-size: 15px;
  font-weight: 800;
}
.m-brief {
  margin: 8px 16px;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ececef;
}
.m-brief h3 { margin: 0 0 6px; font-size: 15px; }
.m-brief p,
.m-brief__sum {
  margin: 0;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.m-brief__sum.is-open {
  display: block;
  -webkit-line-clamp: unset;
}
.m-brief__syms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.m-brief__meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  color: #8b8d98;
  font-size: 11px;
}
</style>
