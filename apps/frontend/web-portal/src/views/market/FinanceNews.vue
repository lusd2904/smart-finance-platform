<template>
  <PageFrame
    title="财经资讯"
    subtitle="市场动态 · 技术扫描 · 外部资讯 · 简报刷新"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="market" @change="load(false)">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" clearable placeholder="关键词过滤标题/摘要/标的" style="width:260px" />
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="load(true)">刷新简报</el-button>
    </template>

    <div class="scan-row" v-if="scanCards.length">
      <article v-for="card in scanCards" :key="card.id || card.market" class="scan-card glass-panel">
        <div class="muted">{{ marketLabel(card.market) }} · 技术扫描</div>
        <div class="scan-score">
          <strong class="numeric">{{ card.payload?.technicalScore ?? card.score ?? '--' }}</strong>
          <span>技术评分</span>
        </div>
        <p>{{ card.summary || '暂无摘要' }}</p>
        <div class="muted">{{ card.generatedAt || card.time || '--' }}</div>
      </article>
    </div>

    <div class="feed-head muted">时间 · 标题 · 来源 · 标签</div>
    <el-empty v-if="!loading && !filtered.length" :description="notice || '暂无资讯，可点击刷新简报'" />
    <article v-for="item in filtered" :key="item.id || item.headline || item.title" class="news-line glass-panel" @click="openItem(item)">
      <div class="news-tags">
        <span class="mkt-tag" :class="`is-${String(item.market || '').toLowerCase()}`">{{ item.market || marketLabel(item.market) }}</span>
        <el-tag size="small" :type="typeTag(item.briefingType || item.type)">{{ typeLabel(item.briefingType || item.type) }}</el-tag>
        <strong>{{ item.headline || item.title }}</strong>
      </div>
      <p>{{ item.summary || item.content || '' }}</p>
      <div class="muted">
        <span>{{ item.sourceName || item.source || 'system' }}</span>
        <span v-if="item.payload?.symbol || item.symbol">关注 {{ item.payload?.symbol || item.symbol }}</span>
        <span>{{ item.generatedAt || item.publishedAt || item.time || '' }}</span>
      </div>
    </article>

    <el-drawer v-model="drawer" :title="current.headline || current.title || '资讯详情'" size="520px">
      <div v-if="current.headline || current.title" class="news-drawer">
        <div class="news-tags">
          <span class="mkt-tag">{{ marketLabel(current.market) }}</span>
          <el-tag size="small" :type="typeTag(current.briefingType || current.type)">{{ typeLabel(current.briefingType || current.type) }}</el-tag>
          <span class="muted">{{ current.generatedAt || current.time || '--' }}</span>
        </div>
        <h3>{{ current.headline || current.title }}</h3>
        <p>{{ current.summary || current.content || '暂无正文摘要' }}</p>
        <div class="muted">
          {{ current.sourceName || current.source || 'system' }}
          <template v-if="current.payload?.symbol || current.symbol"> · 关注 {{ current.payload?.symbol || current.symbol }}</template>
        </div>
      </div>
    </el-drawer>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getFinanceBriefings } from '@/api/market'
import { marketLabel, unwrap, unwrapList } from '@/utils/list'

const TYPE_MAP = {
  'market-insight': '市场动态',
  'market-ai-scan': '技术扫描',
  'market-news': '外部资讯',
  recommendation: '推荐关注',
  internal: '系统简报',
  announcement: '公告',
  discussion: '讨论'
}

const loading = ref(false)
const market = ref('')
const keyword = ref('')
const list = ref([])
const notice = ref('')
const drawer = ref(false)
const current = ref({})

const scanCards = computed(() => list.value.filter((i) => (i.briefingType || i.type) === 'market-ai-scan').slice(0, 3))
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const base = list.value.filter((i) => (i.briefingType || i.type) !== 'market-ai-scan')
  if (!kw) return base
  return base.filter((i) => {
    const blob = [i.headline, i.title, i.summary, i.sourceName, i.source, i.payload?.symbol, i.symbol].filter(Boolean).join(' ').toLowerCase()
    return blob.includes(kw)
  })
})

function typeLabel(t) {
  return TYPE_MAP[t] || t || '资讯'
}
function typeTag(t) {
  const map = { 'market-insight': 'info', 'market-ai-scan': 'warning', 'market-news': 'success', recommendation: 'danger' }
  return map[t] || ''
}
function openItem(item) {
  current.value = { ...item }
  drawer.value = true
}

async function load(refresh = false) {
  loading.value = true
  try {
    const res = await getFinanceBriefings({
      market: market.value || undefined,
      limit: 60,
      refresh: !!refresh
    })
    const data = unwrap(res)
    list.value = data.data || data.items || data.briefings || unwrapList(res)
    notice.value = data.message || data.meta?.message || ''
  } catch {
    list.value = []
    notice.value = '财经资讯源暂时不可用'
  } finally {
    loading.value = false
  }
}

onMounted(() => load(false))
</script>

<style scoped>
.scan-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.scan-card { padding: 12px; display: grid; gap: 6px; }
.scan-score { display: flex; align-items: baseline; gap: 8px; }
.scan-score strong { font-size: 28px; color: var(--accent); }
.scan-card p, .news-line p, .news-drawer p { margin: 0; line-height: 1.6; }
.feed-head { padding: 0 2px; }
.news-line { cursor: pointer; }
.news-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.muted { color: var(--text-secondary); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
.news-drawer h3 { margin: 12px 0; }
@media (max-width: 900px) { .scan-row { grid-template-columns: 1fr; } }
</style>
