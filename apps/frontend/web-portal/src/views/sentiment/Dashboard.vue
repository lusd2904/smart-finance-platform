<template>
  <PageFrame
    class="sentiment-page sentiment-dashboard"
    title="舆情AI分析大盘"
    :subtitle="latestTime ? `最新分析时间：${latestTime}` : ''"
    :loading="loading"
  >
    <template #actions>
      <el-button v-hasPermi="['sentiment:news:collect']" type="primary" :loading="collecting" @click="collect">立即采集</el-button>
      <el-button v-hasPermi="['sentiment:analysis:run']" :loading="analyzing" :disabled="!!rateLimitedUntil" @click="analyze">
        {{ rateLimitedUntil ? `请稍后重试 (${retryLeft}s)` : '立即分析' }}
      </el-button>
      <el-button :loading="loading" @click="refreshAll">刷新</el-button>
    </template>

    <el-alert v-if="usingStub && showStubBanner()" class="stub-alert" title="演示·stub · 非实盘舆情" type="warning" show-icon :closable="false" />
    <el-alert v-if="rateLimitMessage" type="warning" show-icon :closable="false" :title="rateLimitMessage" />

    <MarketIndexStrip ref="indexStripRef" :seed="indices" />

    <div class="kpi-row">
      <article class="kpi-card kpi-blue">
        <div class="kpi-icon"><el-icon><Document /></el-icon></div>
        <div>
          <span>总资讯数</span>
          <strong class="numeric">{{ kpiText(stats.total) }}</strong>
        </div>
      </article>
      <article class="kpi-card kpi-purple">
        <div class="kpi-icon"><el-icon><TrendCharts /></el-icon></div>
        <div>
          <span>今日新增</span>
          <strong class="numeric">{{ kpiText(stats.today) }}</strong>
        </div>
      </article>
      <article class="kpi-card kpi-orange">
        <div class="kpi-icon"><el-icon><Clock /></el-icon></div>
        <div>
          <span>待分析数</span>
          <strong class="numeric">{{ kpiText(stats.unanalyzed) }}</strong>
        </div>
      </article>
    </div>

    <div class="market-strip">
      <article v-for="m in markets" :key="m.key" class="market-card glass-panel" :class="directionClass(m.direction)">
        <div class="market-head">
          <span>{{ m.name }}</span>
          <el-tag v-if="m.direction" size="small" effect="dark" :color="directionColor(m.direction)" class="dir-tag">
            {{ directionLabel(m.direction) }}
          </el-tag>
          <el-tag v-else size="small" type="info">暂无</el-tag>
        </div>
        <strong class="numeric score" :style="{ color: directionColor(m.direction) }">
          {{ rawScore(m.score) }}<small>分</small>
        </strong>
        <p class="reason">{{ m.reason || '暂无分析理由' }}</p>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel trend-card">
      <template #header>
        <div class="card-header">
          <h3>市场情绪分数趋势</h3>
          <span class="muted">最近 24 次分析</span>
        </div>
      </template>
      <div v-show="trend.length" ref="trendRef" class="trend-chart" />
      <p v-if="!trend.length && !loading" class="trend-empty">暂无趋势数据</p>
    </el-card>

    <el-row :gutter="10">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>最新分析摘要</h3></div></template>
          <p v-if="latest.summary" class="summary-text">{{ latest.summary }}</p>
          <el-empty v-else description="暂无分析数据" :image-size="48" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>风险事件</h3></div></template>
          <div v-if="riskEvents.length" class="risk-list">
            <div v-for="(item, i) in riskEvents" :key="i" class="risk-item">
              <el-icon class="risk-icon"><Warning /></el-icon>
              <span>{{ item }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无风险事件" :image-size="48" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="glass-panel">
      <template #header><div class="card-header"><h3>分析历史</h3></div></template>
      <el-table :data="history" size="small" stripe empty-text="暂无分析">
        <el-table-column prop="analysisId" label="编号" width="72" />
        <el-table-column label="分析时间" width="170">
          <template #default="{ row }">
            <span class="numeric">{{ formatTime(row.createTime) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="newsCount" label="资讯条数" width="88" align="center" />
        <el-table-column label="美股" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.usDirection" size="small" effect="dark" :color="directionColor(row.usDirection)" class="dir-tag">
              {{ directionLabel(row.usDirection) }} {{ rawScore(row.usScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="港股" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.hkDirection" size="small" effect="dark" :color="directionColor(row.hkDirection)" class="dir-tag">
              {{ directionLabel(row.hkDirection) }} {{ rawScore(row.hkScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="A股" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.aDirection" size="small" effect="dark" :color="directionColor(row.aDirection)" class="dir-tag">
              {{ directionLabel(row.aDirection) }} {{ rawScore(row.aScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="summary-ellipsis">{{ row.summary || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="modelName" label="模型" width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="72" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="String(row.status) === '0' ? 'success' : 'danger'">
              {{ String(row.status) === '0' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import PageFrame from '@/components/page/PageFrame.vue'
import MarketIndexStrip from '@/components/MarketIndexStrip/index.vue'
import { collectNews, getStats, getTrend, listAnalysis, runAnalysis } from '@/api/sentiment'
import { useUserStore } from '@/store/user'
import { unwrap, unwrapList } from '@/utils/list'
import { isDemoSession, showStubBanner, stubSentimentDashboard } from '@/utils/stubs'
import { useTheme } from '@/composables/useTheme'
import '@/styles/sentiment-pages.scss'
import '@/styles/sentiment-dashboard.scss'

const userStore = useUserStore()
const { activeTheme } = useTheme()
const loading = ref(false)
const collecting = ref(false)
const analyzing = ref(false)
const usingStub = ref(false)
const stats = ref({})
const latest = ref({})
const history = ref([])
const indices = ref([])
const trend = ref([])
const trendRef = ref(null)
const indexStripRef = ref(null)
const rateLimitedUntil = ref(0)
const retryLeft = ref(0)
const rateLimitMessage = ref('')
let retryTimer = null
let chart
let onResize

function demoMode() {
  return isDemoSession(userStore)
}

function kpiText(v) {
  if (v === 0 || v === '0') return 0
  if (v == null || v === '') return '--'
  return v
}

function rawScore(v) {
  if (v === 0 || v === '0') return 0
  if (v == null || v === '') return '--'
  return v
}

function formatTime(v) {
  const s = String(v || '').replace('T', ' ').trim()
  return s ? s.slice(0, 19) : ''
}

function normalizeDirection(direction) {
  if (!direction) return ''
  const d = String(direction).toLowerCase()
  if (d.includes('多') || d.includes('bull') || d.includes('up') || d.includes('涨') || d.includes('positive')) return 'up'
  if (d.includes('空') || d.includes('bear') || d.includes('down') || d.includes('跌') || d.includes('negative')) return 'down'
  return 'flat'
}

function directionColor(direction) {
  const d = normalizeDirection(direction)
  if (d === 'up') return 'var(--stat-up, #f56c6c)'
  if (d === 'down') return 'var(--stat-down, #67c23a)'
  return 'var(--text-secondary, #909399)'
}

function directionLabel(direction) {
  const d = normalizeDirection(direction)
  if (d === 'up') return '利多'
  if (d === 'down') return '利空'
  return direction ? '中性' : ''
}

function directionClass(direction) {
  const d = normalizeDirection(direction)
  if (d === 'up') return 'market-up'
  if (d === 'down') return 'market-down'
  return 'market-flat'
}

function parseRisk(raw) {
  if (!raw) return []
  if (Array.isArray(raw)) return raw.map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed.map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
  } catch {
    /* split plain text */
  }
  return String(raw)
    .split(/[\n;；]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

const latestTime = computed(() => {
  const la = stats.value?.latestAnalysis
  const fromStats = la && typeof la === 'object' ? la.createTime : typeof la === 'string' ? la : ''
  return formatTime(latest.value.createTime || fromStats || history.value[0]?.createTime)
})

const markets = computed(() => [
  { key: 'us', name: '美股三大指数', direction: latest.value.usDirection, score: latest.value.usScore, reason: latest.value.usReason },
  { key: 'hk', name: '港股指数', direction: latest.value.hkDirection, score: latest.value.hkScore, reason: latest.value.hkReason },
  { key: 'a', name: 'A股指数', direction: latest.value.aDirection, score: latest.value.aScore, reason: latest.value.aReason }
])

const riskEvents = computed(() => parseRisk(latest.value.riskEvents))

function applyStub() {
  const stub = stubSentimentDashboard()
  usingStub.value = true
  stats.value = stub.stats
  latest.value = stub.latest
  history.value = stub.history
  trend.value = stub.trend
  indices.value = stub.indices
}

function hasLivePayload() {
  return (
    stats.value.total != null ||
    stats.value.today != null ||
    stats.value.unanalyzed != null ||
    Boolean(latest.value.summary) ||
    history.value.length > 0 ||
    trend.value.length > 0
  )
}

function renderTrend(list) {
  if (!trendRef.value) return
  if (!list.length) {
    if (chart) chart.clear()
    return
  }
  if (!chart) chart = echarts.init(trendRef.value)
  const isLight = document.documentElement.dataset.theme === 'glass-light'
  const ink = isLight ? '#334155' : '#e2e8f0'
  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: { data: ['美股', '港股', 'A股'], top: 0, textStyle: { color: ink, fontSize: 12 } },
      grid: { left: 40, right: 16, top: 32, bottom: 24 },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: list.map((item) => formatTime(item.createTime)),
        axisLabel: { formatter: (v) => (v ? String(v).slice(5, 16) : v), color: ink }
      },
      yAxis: { type: 'value', name: '分数', splitLine: { lineStyle: { opacity: 0.12 } } },
      series: [
        { name: '美股', type: 'line', smooth: true, data: list.map((item) => item.usScore), itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.08 } },
        { name: '港股', type: 'line', smooth: true, data: list.map((item) => item.hkScore), itemStyle: { color: '#e6a23c' }, areaStyle: { opacity: 0.08 } },
        { name: 'A股', type: 'line', smooth: true, data: list.map((item) => item.aScore), itemStyle: { color: '#f56c6c' }, areaStyle: { opacity: 0.08 } }
      ]
    },
    true
  )
  chart.resize()
}

async function getStatsData() {
  const res = await getStats()
  const data = unwrap(res)
  stats.value = data && typeof data === 'object' && !Array.isArray(data) ? data : {}
  if (stats.value.latestAnalysis && typeof stats.value.latestAnalysis === 'object') {
    latest.value = { ...latest.value, ...stats.value.latestAnalysis }
  }
}

async function getLatestAnalysis() {
  const res = await listAnalysis({ pageNum: 1, pageSize: 1, status: '0' })
  const rows = unwrapList(res)
  if (rows[0]) latest.value = { ...latest.value, ...rows[0] }
}

async function getHistory() {
  const res = await listAnalysis({ pageNum: 1, pageSize: 20, status: '0' })
  history.value = unwrapList(res)
}

async function getTrendData() {
  const res = await getTrend(24)
  const raw = unwrap(res)
  trend.value = Array.isArray(raw) ? raw : unwrapList(res)
}

async function load() {
  loading.value = true
  usingStub.value = false
  stats.value = {}
  latest.value = {}
  history.value = []
  trend.value = []
  indices.value = []
  try {
    await Promise.allSettled([getStatsData(), getLatestAnalysis(), getHistory(), getTrendData()])
    if (!hasLivePayload() && demoMode()) applyStub()
  } catch {
    if (demoMode()) applyStub()
  } finally {
    loading.value = false
    await nextTick()
    renderTrend(trend.value)
  }
}

function startRateLimitCooldown(seconds, message) {
  const wait = Math.max(15, Math.min(Number(seconds) || 60, 300))
  rateLimitedUntil.value = Date.now() + wait * 1000
  rateLimitMessage.value = message || 'AI 分析触发限流，请稍后再试，不要连续点击'
  retryLeft.value = wait
  if (retryTimer) clearInterval(retryTimer)
  retryTimer = setInterval(() => {
    const left = Math.ceil((rateLimitedUntil.value - Date.now()) / 1000)
    retryLeft.value = Math.max(0, left)
    if (left <= 0) {
      clearInterval(retryTimer)
      retryTimer = null
      rateLimitedUntil.value = 0
      rateLimitMessage.value = ''
    }
  }, 1000)
}

async function collect() {
  collecting.value = true
  try {
    const res = await collectNews()
    const d = unwrap(res)
    ElMessage.success(res?.msg || (d.accepted ? '已加入后台队列' : '采集任务已触发'))
    if (!d.accepted) refreshAll()
  } catch (e) {
    if (usingStub.value) ElMessage.success('已采集（演示·stub）')
    else ElMessage.error(e?.message || '采集失败')
  } finally {
    collecting.value = false
  }
}

async function analyze() {
  if (rateLimitedUntil.value && Date.now() < rateLimitedUntil.value) return
  analyzing.value = true
  try {
    const res = await runAnalysis()
    const data = unwrap(res)
    if (data.rateLimited || data.code === 429) {
      startRateLimitCooldown(data.retryAfter, data.message)
      return
    }
    const msg = data.message || res?.msg || ''
    if (msg.includes('限流') || msg.includes('过于频繁')) {
      startRateLimitCooldown(60, msg)
      return
    }
    ElMessage.success(msg || (data.accepted ? '已加入后台队列' : 'AI分析任务已触发'))
    if (!data.accepted) refreshAll()
  } catch (e) {
    const text = String(e?.message || e || '')
    if (text.includes('429') || text.includes('限流') || text.includes('过于频繁')) {
      startRateLimitCooldown(60, 'AI 分析触发限流，请稍后再试，不要连续点击')
      return
    }
    if (usingStub.value) ElMessage.success('已分析（演示·stub）')
    else ElMessage.error(text || '分析失败')
  } finally {
    analyzing.value = false
  }
}

function refreshAll() {
  load()
  indexStripRef.value && indexStripRef.value.loadQuotes()
}

watch(activeTheme, async () => {
  await nextTick()
  renderTrend(trend.value)
})

onMounted(() => {
  refreshAll()
  onResize = () => chart && chart.resize()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  if (retryTimer) clearInterval(retryTimer)
  if (onResize) window.removeEventListener('resize', onResize)
  if (chart) chart.dispose()
})
</script>

<style scoped>
.stub-alert {
  margin: 0;
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.kpi-card {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 52px;
  padding: 6px 10px;
  border-radius: 8px;
  color: #fff;
}
.kpi-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.22);
  font-size: 16px;
}
.kpi-card span {
  display: block;
  font-size: 12px;
  opacity: 0.92;
}
.kpi-card strong {
  display: block;
  font-size: 16px;
  line-height: 1.15;
}
.kpi-blue {
  background: linear-gradient(135deg, #409eff 0%, #2d6cdf 100%);
}
.kpi-purple {
  background: linear-gradient(135deg, #9254de 0%, #6a3fd0 100%);
}
.kpi-orange {
  background: linear-gradient(135deg, #f0a020 0%, #e0701a 100%);
}
.market-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.market-card {
  display: grid;
  gap: 4px;
  padding: 8px 10px !important;
}
.market-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-emphasis);
}
.dir-tag {
  border: none;
  color: #fff;
}
.score {
  font-size: 16px !important;
  line-height: 1.2;
}
.score small {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
}
.reason {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.market-up {
  border-top: 3px solid var(--stat-up, #f56c6c);
}
.market-down {
  border-top: 3px solid var(--stat-down, #67c23a);
}
.market-flat {
  border-top: 3px solid #909399;
}
.card-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
h3 {
  margin: 0;
  font-size: 16px;
}
.muted {
  color: var(--text-secondary);
  font-size: 12px;
}
.trend-chart {
  width: 100%;
  height: 156px;
  max-height: 156px;
  min-height: 156px;
}
.trend-empty {
  margin: 0;
  height: 64px;
  max-height: 80px;
  min-height: 56px;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: var(--text-secondary);
}
.summary-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--text-emphasis);
}
.risk-list {
  display: grid;
  gap: 6px;
}
.risk-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--warning) 12%, transparent);
  color: var(--warning);
  font-size: 13px;
  line-height: 1.5;
}
.risk-icon {
  margin-top: 2px;
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .kpi-row,
  .market-strip {
    grid-template-columns: 1fr;
  }
}
</style>
