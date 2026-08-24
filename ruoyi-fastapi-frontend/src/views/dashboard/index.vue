<template>
  <div class="home-page" v-loading="loading">
    <!-- 顶栏：问候 + 三市场开闭市 + 刷新 -->
    <HeroBar :summary="summary" :loading="loading" @refresh="refreshAll(true)" class="mb16" />

    <!-- 资产条 -->
    <AssetStrip :section="summary.asset" class="mb16" />

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
const loading = ref(false)
const summary = ref({})

async function refreshAll(force = false) {
  loading.value = true
  try {
    const res = await getDashboardSummary(force ? { refresh: true } : {})
    summary.value = res.data || {}
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

@media (max-width: 768px) {
  .home-page {
    padding: 12px;
  }
}
</style>
