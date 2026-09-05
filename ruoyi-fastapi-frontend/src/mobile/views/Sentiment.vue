<template>
  <div class="m-page">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <h2 class="m-page-title">舆情</h2>
      <EmptyState v-if="error && !analysis" :message="error" retry @retry="load" />
      <template v-else>
        <section class="m-card">
          <div class="m-card__h">市场研判</div>
          <p class="m-summary">{{ analysis?.summary || '暂无摘要' }}</p>
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
              <li v-for="(ev, i) in riskEvents" :key="i">{{ ev }}</li>
            </ul>
          </div>
        </section>
        <section>
          <div class="m-sec-title">简报</div>
          <EmptyState v-if="!briefings.length && !loading" message="暂无简报" />
          <article v-for="item in briefings" :key="item.id || item.headline" class="m-brief">
            <h3>{{ item.headline }}</h3>
            <p>{{ item.summary }}</p>
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
import { fmtTime } from '../utils/format'
import { unwrapData, unwrapRows } from '../utils/payload'
import { parseRiskEvents, sentimentDirection, sentimentIndexTo100 } from '../utils/riskEvents'

const analysis = ref(null)
const briefings = ref([])
const error = ref('')
const loading = ref(false)
const refreshing = ref(false)

const DIR_LABEL = { up: '利多', down: '利空', flat: '中性', unknown: '—' }

const riskEvents = computed(() => parseRiskEvents(analysis.value?.riskEvents))

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

async function loadBriefings() {
  const res = await getFinanceBriefings({ limit: 40 })
  const payload = unwrapData(res)
  const items = payload.data || payload.items || []
  briefings.value = items.map((it) => ({
    id: it.id,
    headline: it.headline,
    summary: it.summary,
    sourceName: it.sourceName,
    generatedAt: it.generatedAt
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
}
.m-mkts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
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
.m-brief p { margin: 0; color: #4b5563; font-size: 13px; line-height: 1.5; }
.m-brief__meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  color: #8b8d98;
  font-size: 11px;
}
</style>
