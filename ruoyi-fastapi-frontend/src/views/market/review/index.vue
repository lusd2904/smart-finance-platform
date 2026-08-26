<template>
  <div class="app-container review-page">
    <div class="page-hero">
      <div>
        <h2>市场分析</h2>
        <p>美股、港股、A股收盘复盘。亚太 16:35、美股北京时间约 05:15 自动生成，也可立即分析。</p>
      </div>
      <div class="acts">
        <el-radio-group v-model="market" @change="loadHistory">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="US">美股</el-radio-button>
          <el-radio-button label="HK">港股</el-radio-button>
          <el-radio-button label="CN">A股</el-radio-button>
        </el-radio-group>
        <el-button type="success" :loading="analyzing" @click="handleAnalyze" v-hasPermi="['market:review:analyze']">立即分析</el-button>
        <el-button icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="latest.aiHint" :title="latest.aiHint" type="warning" show-icon class="mb16" :closable="false" />

    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :md="8" v-for="item in latest.items || []" :key="item.market">
        <el-card shadow="never" class="latest-card" :class="stanceClass(item.stance)" @click="selectRow(item)">
          <div class="latest-head">
            <strong>{{ item.marketLabel }}</strong>
            <el-tag size="small" :type="stanceType(item.stance)" effect="dark">{{ item.stance || '待分析' }}</el-tag>
          </div>
          <div class="latest-date">{{ item.tradeDate || '--' }} · 温度 {{ item.score != null ? item.score : '--' }}</div>
          <p class="latest-summary">{{ item.summary || '暂无报告' }}</p>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">历史记录</span>
              <span class="panel-sub">每天每个市场一条</span>
            </div>
          </template>
          <el-table :data="history" highlight-current-row @row-click="selectRow">
            <el-table-column prop="tradeDate" label="交易日" width="120" />
            <el-table-column label="市场" width="80">
              <template #default="{row}">{{ row.marketLabel }}</template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="立场" width="80" align="center">
              <template #default="{row}">
                <el-tag size="small" :type="stanceType(row.stance)">{{ row.stance || '--' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="score" label="温度" width="70" align="center" />
            <el-table-column prop="analysisTime" label="生成时间" width="170" />
          </el-table>
          <el-empty v-if="!history.length && !loading" description="还没有复盘，点击「立即分析」生成" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" v-if="current">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">{{ current.marketLabel }} {{ current.tradeDate }}</span>
              <el-tag size="small" :type="stanceType(current.stance)" effect="dark">{{ current.stance }}</el-tag>
            </div>
          </template>
          <h3 class="report-title">{{ current.title }}</h3>
          <p class="report-body">{{ current.summary }}</p>
          <div class="report-block" v-if="current.indexReview"><h4>指数 / 代表股</h4><p>{{ current.indexReview }}</p></div>
          <div class="report-block" v-if="current.newsReview"><h4>资讯</h4><p>{{ current.newsReview }}</p></div>
          <div class="report-block" v-if="current.sentimentReview"><h4>舆情</h4><p>{{ current.sentimentReview }}</p></div>
          <div class="report-block" v-if="current.outlook"><h4>次日关注</h4><p>{{ current.outlook }}</p></div>
          <p class="risk" v-if="current.riskWarning">风险：{{ current.riskWarning }}</p>
          <div class="muted">{{ current.source === 'ai' ? 'AI 复盘' : '指标兜底' }} · {{ current.analysisTime }}</div>
        </el-card>
        <el-card shadow="never" v-else>
          <el-empty description="选择一条历史查看全文" :image-size="72" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="MarketReview">
import { getMarketReviewLatest, getMarketReviewHistory, analyzeMarketReview, pollMarketJob } from '@/api/market'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const analyzing = ref(false)
const market = ref('')
const latest = ref({ items: [] })
const history = ref([])
const current = ref(null)

function stanceType(stance) {
  if (stance === '偏多') return 'danger'
  if (stance === '偏空') return 'success'
  return 'info'
}
function stanceClass(stance) {
  if (stance === '偏多') return 'bull'
  if (stance === '偏空') return 'bear'
  return 'neutral'
}
function selectRow(row) {
  current.value = row
}

async function loadLatest() {
  const res = await getMarketReviewLatest()
  latest.value = res.data || { items: [] }
}

async function loadHistory() {
  loading.value = true
  try {
    const res = await getMarketReviewHistory({ market: market.value || undefined, limit: 90 })
    history.value = res.data?.items || []
    if (current.value) {
      const hit = history.value.find(r => r.reviewId === current.value.reviewId)
      current.value = hit || history.value[0] || current.value
    } else {
      current.value = history.value[0] || (latest.value.items || [])[0] || null
    }
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  await loadLatest()
  await loadHistory()
}

async function handleAnalyze() {
  analyzing.value = true
  try {
    const res = await analyzeMarketReview(market.value || undefined)
    const d = res.data || {}
    if (d.accepted || d.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队')
      if (d.jobId) {
        const ticket = await pollMarketJob(d.jobId)
        if (ticket.status === 'failed') {
          proxy.$modal.msgError(ticket.error || '分析失败')
          return
        }
      }
      await loadAll()
      return
    }
    proxy.$modal.msgSuccess(res.msg || '分析完成')
    await loadAll()
  } finally {
    analyzing.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.page-hero { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: #909399; font-size: 13px; max-width: 640px; }
}
.acts { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.mb16 { margin-bottom: 16px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-title { font-weight: 600; }
.panel-sub { font-size: 12px; color: #909399; }
.latest-card { border-radius: 14px; margin-bottom: 12px; cursor: pointer; min-height: 160px;
  &.bull { border-color: #fecaca; }
  &.bear { border-color: #bbf7d0; }
}
.latest-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.latest-date { font-size: 12px; color: #64748b; margin-bottom: 8px; }
.latest-summary { margin: 0; line-height: 1.7; color: #334155; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.report-title { margin: 0 0 8px; font-size: 16px; }
.report-body, .report-block p { margin: 0; line-height: 1.8; color: #475569; white-space: pre-wrap; }
.report-block { margin-top: 12px; h4 { margin: 0 0 4px; font-size: 13px; color: #64748b; } }
.risk { margin-top: 12px; color: #b45309; }
.muted { margin-top: 12px; font-size: 12px; color: #94a3b8; }
</style>
