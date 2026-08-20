<template>
  <div class="app-container finance-news">
    <div class="toolbar">
      <el-radio-group v-model="market" size="default" @change="loadData">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="US">美股</el-radio-button>
        <el-radio-button label="CN">A股</el-radio-button>
        <el-radio-button label="HK">港股</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="keyword"
        clearable
        placeholder="关键词过滤标题/摘要/标的"
        style="width: 260px; margin-left: 12px"
        @keyup.enter="filterLocal"
      />
      <el-button type="primary" icon="Refresh" :loading="loading" style="margin-left: 12px" @click="handleRefresh" v-hasPermi="['market:finance:list']">
        刷新简报
      </el-button>
    </div>

    <!-- 市场扫描卡片 -->
    <el-row :gutter="16" class="mb16 scan-row" v-if="scanCards.length">
      <el-col :xs="24" :sm="8" v-for="(card, idx) in scanCards" :key="card.market + '-' + idx">
        <el-card shadow="hover" class="scan-card">
          <div class="scan-market">{{ marketLabel(card.market) }} · 技术扫描</div>
          <div class="scan-score">
            <span class="score-num">{{ (card.payload && card.payload.technicalScore) != null ? card.payload.technicalScore : '--' }}</span>
            <span class="score-unit">技术评分</span>
          </div>
          <div class="scan-summary">{{ card.summary || '暂无摘要' }}</div>
          <div class="scan-time">{{ card.generatedAt || '--' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 资讯卡片流 -->
    <el-alert
      v-if="notice"
      class="mb16"
      type="info"
      show-icon
      :closable="false"
      :title="notice"
    />
    <div v-loading="loading">
      <el-empty v-if="!loading && filteredList.length === 0" :description="notice || '暂无资讯，可点击刷新简报'" />
      <div v-for="item in filteredList" :key="item.id" class="news-card">
        <div class="news-tags">
          <el-tag size="small" effect="plain">{{ marketLabel(item.market) }}</el-tag>
          <el-tag size="small" :type="typeTag(item.briefingType)" style="margin-left: 6px">{{ typeLabel(item.briefingType) }}</el-tag>
        </div>
        <div class="news-title">
          <el-link type="primary" :underline="false" @click="openContent(item)">{{ item.headline }}</el-link>
        </div>
        <div class="news-summary">{{ item.summary }}</div>
        <div class="news-meta">
          <span>{{ item.sourceName || 'system' }}</span>
          <span v-if="item.payload && item.payload.symbol" class="focus">关注 {{ item.payload.symbol }}</span>
          <span>{{ item.generatedAt }}</span>
        </div>
      </div>
    </div>

    <el-drawer v-model="drawerVisible" :title="currentItem.headline || '资讯详情'" size="520px" destroy-on-close>
      <div class="news-drawer" v-if="currentItem">
        <div class="meta-row">
          <el-tag size="small" effect="plain">{{ marketLabel(currentItem.market) }}</el-tag>
          <el-tag size="small" :type="typeTag(currentItem.briefingType)" style="margin-left: 6px">{{ typeLabel(currentItem.briefingType) }}</el-tag>
          <span class="meta-time">{{ currentItem.generatedAt || '--' }}</span>
        </div>
        <h3 class="drawer-title">{{ currentItem.headline }}</h3>
        <div class="drawer-body">{{ currentItem.summary || '暂无正文摘要' }}</div>
        <div class="drawer-footer">
          <span>{{ currentItem.sourceName || 'system' }}</span>
          <span v-if="currentItem.payload && currentItem.payload.symbol"> · 关注 {{ currentItem.payload.symbol }}</span>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup name="MarketFinanceNewsIndex">
import { getFinanceBriefings } from '@/api/market'

const { proxy } = getCurrentInstance()

const market = ref('')
const keyword = ref('')
const loading = ref(false)
const list = ref([])
const notice = ref('')
const drawerVisible = ref(false)
const currentItem = ref({})

const TYPE_MAP = {
  'market-insight': '市场动态',
  'market-ai-scan': '技术扫描',
  'market-news': '外部资讯',
  recommendation: '推荐关注',
  internal: '系统简报',
  announcement: '公告',
  discussion: '讨论'
}

const filteredList = computed(() => {
  const kw = (keyword.value || '').trim().toLowerCase()
  const base = list.value.filter(i => i.briefingType !== 'market-ai-scan')
  if (!kw) return base
  return base.filter(i => {
    const blob = [i.headline, i.summary, i.sourceName, i.payload?.symbol].filter(Boolean).join(' ').toLowerCase()
    return blob.includes(kw)
  })
})

const scanCards = computed(() => list.value.filter(i => i.briefingType === 'market-ai-scan').slice(0, 3))

function marketLabel(m) {
  return { US: '美股', CN: 'A股', HK: '港股' }[m] || m || '--'
}
function typeLabel(t) {
  return TYPE_MAP[t] || t || '资讯'
}
function typeTag(t) {
  const map = {
    'market-insight': 'info',
    'market-ai-scan': 'warning',
    'market-news': 'success',
    recommendation: 'danger'
  }
  return map[t] || ''
}
function openContent(item) {
  currentItem.value = { ...item }
  drawerVisible.value = true
}
function filterLocal() {
  // computed 自动处理
}

function loadData(refresh = false) {
  loading.value = true
  getFinanceBriefings({
    market: market.value || undefined,
    limit: 60,
    refresh: !!refresh
  })
    .then(res => {
      const payload = res.data || {}
      list.value = payload.data || payload.items || []
      notice.value = payload.message || payload.meta?.message || ''
    })
    .catch(() => {
      list.value = []
      notice.value = '财经资讯源暂时不可用，已返回空列表，请稍后重试'
    })
    .finally(() => {
      loading.value = false
    })
}

function handleRefresh() {
  loadData(true)
}

onMounted(() => loadData(false))
</script>

<style lang="scss" scoped>
.finance-news {
  .mb16 {
    margin-bottom: 16px;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 16px;
  }
  .scan-card {
    border-radius: 12px;
    margin-bottom: 12px;
    .scan-market {
      font-size: 13px;
      color: #909399;
      margin-bottom: 8px;
    }
    .scan-score {
      display: flex;
      align-items: baseline;
      gap: 8px;
      margin-bottom: 8px;
      .score-num {
        font-size: 28px;
        font-weight: 700;
        color: #409eff;
      }
      .score-unit {
        font-size: 12px;
        color: #909399;
      }
    }
    .scan-summary {
      font-size: 13px;
      color: #606266;
      line-height: 1.5;
      min-height: 40px;
    }
    .scan-time {
      margin-top: 8px;
      font-size: 12px;
      color: #c0c4cc;
    }
  }
  .news-card {
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-lighter);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
    .news-tags {
      margin-bottom: 8px;
    }
    .news-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 6px;
      line-height: 1.4;
    }
    .news-summary {
      font-size: 13px;
      color: #606266;
      line-height: 1.6;
      margin-bottom: 8px;
    }
    .news-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 12px;
      color: #909399;
      .focus {
        color: #e6a23c;
      }
    }
  }
  .news-drawer {
    .meta-row {
      display: flex;
      align-items: center;
      margin-bottom: 12px;
      .meta-time {
        margin-left: auto;
        color: #909399;
        font-size: 13px;
      }
    }
    .drawer-title {
      margin: 0 0 16px;
      font-size: 18px;
      line-height: 1.5;
      word-break: break-word;
    }
    .drawer-body {
      font-size: 14px;
      line-height: 1.8;
      color: var(--text-emphasis, #303133);
      white-space: pre-wrap;
      word-break: break-word;
    }
    .drawer-footer {
      margin-top: 20px;
      padding-top: 12px;
      border-top: 1px solid #ebeef5;
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
