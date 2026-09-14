<template>
  <PageFrame
    title="市场分析"
    subtitle="三市场收盘复盘 · 立即分析"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
      </el-radio-group>
      <el-button type="success" :loading="analyzing" @click="analyze">立即分析</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="latest-row">
      <article
        v-for="item in latest"
        :key="item.market"
        class="latest-card glass-panel"
        :class="stanceClass(item.stance)"
        @click="selectRow(item)"
      >
        <div class="latest-head">
          <strong>{{ item.marketLabel || item.market }}</strong>
          <el-tag size="small" :type="stanceType(item.stance)" effect="dark">{{ item.stance || '待分析' }}</el-tag>
        </div>
        <div class="muted">{{ item.tradeDate || '--' }} · 温度 <b class="numeric">{{ item.score ?? '--' }}</b></div>
        <p>{{ item.summary || '暂无报告' }}</p>
      </article>
    </div>

    <el-row :gutter="12">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>历史记录</h3>
              <span class="muted">每天每个市场一条 · CTA 查看全文</span>
            </div>
          </template>
          <el-table :data="history" stripe highlight-current-row empty-text="暂无记录" @row-click="selectRow">
            <el-table-column prop="analysisTime" label="生成时间" width="170" />
            <el-table-column prop="tradeDate" label="交易日" width="120" />
            <el-table-column label="市场" width="80">
              <template #default="{ row }">{{ row.marketLabel || row.market }}</template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="立场" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="stanceType(row.stance)">{{ row.stance || '--' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="score" label="温度" width="70" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="glass-panel" v-if="current">
          <template #header>
            <div class="card-header">
              <h3>{{ current.marketLabel || current.market }} {{ current.tradeDate }}</h3>
              <el-button type="primary" link @click="exportReport">导出</el-button>
            </div>
          </template>
          <h4>{{ current.title }}</h4>
          <p>{{ current.summary }}</p>
          <div v-if="current.indexReview" class="block"><h5>指数 / 代表股</h5><p>{{ current.indexReview }}</p></div>
          <div v-if="current.newsReview" class="block"><h5>资讯</h5><p>{{ current.newsReview }}</p></div>
          <div v-if="current.sentimentReview" class="block"><h5>舆情</h5><p>{{ current.sentimentReview }}</p></div>
          <div v-if="current.outlook" class="block"><h5>次日关注</h5><p>{{ current.outlook }}</p></div>
          <p v-if="current.riskWarning" class="risk">风险：{{ current.riskWarning }}</p>
        </el-card>
        <el-card v-else shadow="never" class="glass-panel">
          <el-empty description="选择一条历史查看全文" :image-size="72" />
        </el-card>
      </el-col>
    </el-row>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { analyzeMarketReview, getMarketReviewHistory, getMarketReviewLatest } from '@/api/market'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const analyzing = ref(false)
const market = ref('')
const latest = ref([])
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

async function load() {
  loading.value = true
  try {
    const [latestRes, histRes] = await Promise.allSettled([
      getMarketReviewLatest(),
      getMarketReviewHistory({ market: market.value || undefined, limit: 90 })
    ])
    if (latestRes.status === 'fulfilled') {
      const data = unwrap(latestRes.value)
      latest.value = data.items || unwrapList(latestRes.value)
    }
    if (histRes.status === 'fulfilled') {
      history.value = unwrap(histRes.value).items || unwrapList(histRes.value)
    }
    if (!current.value) current.value = history.value[0] || latest.value[0] || null
  } catch {
    latest.value = []
    history.value = []
  } finally {
    loading.value = false
  }
}

async function analyze() {
  analyzing.value = true
  try {
    await analyzeMarketReview(market.value || undefined)
    ElMessage.success('已提交')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

function exportReport() {
  if (!current.value) return
  const t = current.value
  const body = [
    `# ${t.title || '市场复盘'}`,
    '',
    `${t.marketLabel || t.market} · ${t.tradeDate || ''} · ${t.stance || ''} · 温度 ${t.score ?? '--'}`,
    '',
    t.summary || '',
    t.indexReview ? `\n## 指数 / 代表股\n${t.indexReview}` : '',
    t.newsReview ? `\n## 资讯\n${t.newsReview}` : '',
    t.sentimentReview ? `\n## 舆情\n${t.sentimentReview}` : '',
    t.outlook ? `\n## 次日关注\n${t.outlook}` : '',
    t.riskWarning ? `\n风险：${t.riskWarning}` : ''
  ].filter(Boolean).join('\n')
  const blob = new Blob([body], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `review-${t.market || 'all'}-${t.tradeDate || 'latest'}.md`
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(load)
</script>

<style scoped>
.latest-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.latest-card { padding: 12px; cursor: pointer; display: grid; gap: 6px; }
.latest-card.bull { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--stat-up) 35%, transparent); }
.latest-card.bear { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--stat-down) 35%, transparent); }
.latest-head { display: flex; justify-content: space-between; align-items: center; }
.latest-card p, .block p { margin: 0; line-height: 1.7; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3, h3, h4, h5 { margin: 0; }
h4 { margin-bottom: 8px; }
.block { margin-top: 12px; }
.block h5 { color: var(--text-secondary); font-size: 12px; margin-bottom: 4px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.risk { color: var(--warning); }
@media (max-width: 900px) { .latest-row { grid-template-columns: 1fr; } }
</style>
