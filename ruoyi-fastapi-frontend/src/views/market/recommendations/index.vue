<template>
  <div class="app-container rec-page">
    <div class="page-hero">
      <div>
        <h2>智能推荐</h2>
        <p>聚合财经简报、舆情综述与关注信号（站内内容，不跳转外链）</p>
      </div>
      <el-button type="primary" icon="Refresh" :loading="loading" @click="loadAll">刷新推荐</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="panel" v-loading="loading">
          <template #header><span class="panel-title">市场简报推荐</span></template>
          <el-empty v-if="!briefings.length" description="暂无简报" />
          <div v-for="item in briefings" :key="item.id || item.headline" class="rec-item" @click="openBrief(item)">
            <div class="rec-title">{{ item.headline || item.title }}</div>
            <div class="rec-summary">{{ item.summary || '暂无摘要' }}</div>
            <div class="rec-meta">
              <el-tag size="small" effect="plain">{{ item.market || 'ALL' }}</el-tag>
              <span>{{ item.sourceName || item.briefingType || 'briefing' }}</span>
              <span>{{ item.generatedAt || '' }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="panel mb16" v-loading="loading">
          <template #header><span class="panel-title">最新舆情研判</span></template>
          <template v-if="latest.summary">
            <div class="score-line">
              <span>美 {{ latest.usScore ?? '--' }}</span>
              <span>港 {{ latest.hkScore ?? '--' }}</span>
              <span>A {{ latest.aScore ?? '--' }}</span>
            </div>
            <div class="rec-summary">{{ latest.summary }}</div>
            <el-button type="primary" link @click="$router.push('/sentiment/dashboard')">打开舆情大盘</el-button>
          </template>
          <el-empty v-else description="暂无舆情分析" />
        </el-card>
        <el-card shadow="never" class="panel" v-loading="loading">
          <template #header><span class="panel-title">关注资讯</span></template>
          <div v-for="n in news" :key="n.newsId" class="rec-item" @click="openNews(n)">
            <div class="rec-title">{{ n.title }}</div>
            <div class="rec-summary">{{ (n.content || n.title || '').slice(0, 120) }}</div>
          </div>
          <el-empty v-if="!news.length" description="暂无资讯" />
        </el-card>
      </el-col>
    </el-row>

    <el-drawer v-model="drawer" :title="current.title || '推荐详情'" size="480px">
      <div class="drawer-body">{{ current.body || '暂无内容' }}</div>
    </el-drawer>
  </div>
</template>

<script setup name="MarketRecommendations">
import { getFinanceBriefings } from '@/api/market'
import { getStats, listNews } from '@/api/sentiment'

const loading = ref(false)
const briefings = ref([])
const news = ref([])
const latest = ref({})
const drawer = ref(false)
const current = ref({})

function openBrief(item) {
  current.value = { title: item.headline || item.title, body: item.summary || '暂无摘要' }
  drawer.value = true
}
function openNews(n) {
  current.value = { title: n.title, body: n.content || n.title }
  drawer.value = true
}

async function loadAll() {
  loading.value = true
  try {
    const [b, s, n] = await Promise.all([
      getFinanceBriefings({ limit: 20, refresh: false }).catch(() => ({ data: {} })),
      getStats().catch(() => ({ data: {} })),
      listNews({ pageNum: 1, pageSize: 8 }).catch(() => ({ rows: [] }))
    ])
    const payload = b.data || {}
    briefings.value = payload.data || payload.items || []
    latest.value = (s.data && s.data.latestAnalysis) || {}
    news.value = n.rows || []
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.page-hero {
  display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: #909399; font-size: 13px; }
}
.panel { border-radius: 14px; margin-bottom: 16px; }
.panel-title { font-weight: 600; }
.rec-item {
  padding: 12px 0; border-bottom: 1px solid #f1f5f9; cursor: pointer;
  &:hover .rec-title { color: #6366f1; }
}
.rec-title { font-weight: 600; margin-bottom: 6px; }
.rec-summary { font-size: 13px; color: #64748b; line-height: 1.6; }
.rec-meta { display: flex; gap: 10px; margin-top: 8px; font-size: 12px; color: #94a3b8; align-items: center; }
.score-line { display: flex; gap: 14px; margin-bottom: 10px; font-weight: 700; }
.drawer-body { white-space: pre-wrap; line-height: 1.8; color: #334155; }
.mb16 { margin-bottom: 16px; }
</style>
