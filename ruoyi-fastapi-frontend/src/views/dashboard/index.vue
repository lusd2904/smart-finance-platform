<template>
  <div class="home-page" v-loading="loading">
    <!-- 顶栏：问候 + 三市场开闭市 + 刷新 -->
    <HeroBar :summary="summary" :loading="loading" @refresh="refreshAll(true)" class="mb16" />

    <!-- 资产条 -->
    <AssetStrip :section="summary.asset" class="mb16" />

    <el-card shadow="never" class="panel-card mb16" v-loading="reviewLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">市场分析</span>
          <span class="panel-sub">美股 · 港股 · A股 收盘复盘</span>
          <el-button link type="primary" @click="go('/market/review')">历史记录</el-button>
        </div>
      </template>
      <el-row :gutter="12" v-if="marketReviews.length">
        <el-col :xs="24" :md="8" v-for="item in marketReviews" :key="item.market">
          <div class="review-card" :class="reviewTone(item.stance)" @click="go('/market/review')">
            <div class="review-head">
              <strong>{{ item.marketLabel }}</strong>
              <el-tag size="small" :type="reviewTag(item.stance)" effect="dark">{{ item.stance || '待分析' }}</el-tag>
            </div>
            <div class="review-meta">{{ item.tradeDate || '--' }} · 温度 {{ item.score != null ? item.score : '--' }}</div>
            <p class="review-summary">{{ item.summary || '暂无当日复盘' }}</p>
          </div>
        </el-col>
      </el-row>
      <el-empty v-else description="暂无收盘复盘，可到行情中心「市场分析」立即生成" :image-size="72">
        <el-button type="primary" @click="go('/market/review')">去市场分析</el-button>
      </el-empty>
    </el-card>

    <!-- 快捷导航（压缩一行） -->
    <el-card shadow="never" class="panel-card mb16">
      <QuickNav />
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <AiVerdict :section="summary.sentiment" class="mb16 block-gap" />
        <BriefingStream :section="summary.briefings" class="mb16 block-gap" />
      </el-col>
      <el-col :xs="24" :lg="10">
        <HeatSummary :section="summary.heat" class="mb16 block-gap" />
        <WatchSignals :section="summary.watchSignals" class="mb16 block-gap" />
        <QuoteBoard :section="summary.quotes" class="mb16 block-gap" />
        <SystemHealth :section="summary.health" class="block-gap" />
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="Index">
import { getDashboardSummary } from '@/api/dashboard'
import { getMarketReviewLatest } from '@/api/market'
import HeroBar from './components/HeroBar.vue'
import AssetStrip from './components/AssetStrip.vue'
import QuickNav from './components/QuickNav.vue'
import AiVerdict from './components/AiVerdict.vue'
import BriefingStream from './components/BriefingStream.vue'
import HeatSummary from './components/HeatSummary.vue'
import WatchSignals from './components/WatchSignals.vue'
import QuoteBoard from './components/QuoteBoard.vue'
import SystemHealth from './components/SystemHealth.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const reviewLoading = ref(false)
const summary = ref({})
const marketReviews = ref([])

function go(path) {
  if (!path) return
  router.push(path).catch(() => {})
}

function reviewTag(stance) {
  if (stance === '偏多') return 'danger'
  if (stance === '偏空') return 'success'
  return 'info'
}

function reviewTone(stance) {
  if (stance === '偏多') return 'bull'
  if (stance === '偏空') return 'bear'
  return 'neutral'
}

async function loadMarketReviews() {
  reviewLoading.value = true
  try {
    const res = await getMarketReviewLatest()
    marketReviews.value = (res.data && res.data.items) || []
  } catch {
    marketReviews.value = []
  } finally {
    reviewLoading.value = false
  }
}

async function refreshAll(force = false) {
  loading.value = true
  try {
    const res = await getDashboardSummary(force ? { refresh: true } : {})
    summary.value = res.data || {}
    await loadMarketReviews()
  } catch {
    /* 聚合接口失败时保持空态，各组件自行展示占位 */
  } finally {
    loading.value = false
  }
}

let pollTimer = null

onMounted(() => {
  refreshAll()
  // 5 分钟静默轮询；命中后端 30s 缓存，成本可忽略
  pollTimer = setInterval(() => refreshAll(false), 5 * 60 * 1000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})

// 从行情中心等页面带 ?market=US 返回时自动刷新一次
watch(
  () => route.query,
  (q, prev) => {
    if (prev && q.t !== prev.t) refreshAll(false)
  }
)
</script>

<style scoped lang="scss">
.home-page {
  padding: 16px;
  min-height: calc(100vh - 120px);
  background: linear-gradient(180deg, var(--page-bg) 0%, var(--surface-soft) 220px, var(--page-bg) 100%);
  color: var(--text-emphasis);
}

.mb16 {
  margin-bottom: 16px;
}

.block-gap {
  margin-bottom: 16px;
}

.panel-card {
  border-radius: 14px;
  border: 1px solid var(--border-soft, #eef2ff);
  :deep(.el-card__header) {
    border-bottom: 1px solid #f1f5f9;
    padding: 14px 18px;
  }
  :deep(.el-card__body) {
    padding: 16px 18px;
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
}

.panel-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
  margin-right: 8px;
}

.review-card {
  border-radius: 12px;
  padding: 14px;
  min-height: 168px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  margin-bottom: 8px;
  &.bull { border-color: #fecaca; }
  &.bear { border-color: #bbf7d0; }
}

.review-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.review-meta {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.review-summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #334155;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (max-width: 768px) {
  .home-page {
    padding: 12px;
  }
}
</style>
