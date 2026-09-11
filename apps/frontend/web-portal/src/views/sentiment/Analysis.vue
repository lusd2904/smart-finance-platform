<template>
  <PageFrame class="sentiment-page" title="分析历史" badge="「分析历史 /sentiment/analysis」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="analyzing" @click="analyze">手动分析</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-card shadow="never" class="glass-panel filter-card">
      <el-form :inline="true" class="compact-form" @submit.prevent="search">
        <el-form-item label="状态">
          <el-select v-model="query.status" clearable placeholder="分析状态" style="width: 120px">
            <el-option label="成功" value="0" />
            <el-option label="失败" value="1" />
          </el-select>
        </el-form-item>
        <el-form-item label="分析时间">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" size="small" stripe empty-text="暂无分析" style="cursor: pointer" @row-click="openDetail">
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
              {{ directionLabel(row.usDirection) }} {{ scoreText(row.usScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="港股" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.hkDirection" size="small" effect="dark" :color="directionColor(row.hkDirection)" class="dir-tag">
              {{ directionLabel(row.hkDirection) }} {{ scoreText(row.hkScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="A股" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.aDirection" size="small" effect="dark" :color="directionColor(row.aDirection)" class="dir-tag">
              {{ directionLabel(row.aDirection) }} {{ scoreText(row.aScore) }}
            </el-tag>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
        <el-table-column prop="modelName" label="模型" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="isOk(row) ? 'success' : 'danger'">{{ isOk(row) ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="72" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="open" title="分析详情" width="760px" append-to-body>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="分析时间">{{ formatTime(detail.createTime) || '--' }}</el-descriptions-item>
        <el-descriptions-item label="资讯条数">{{ detail.newsCount ?? '--' }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ detail.modelName || '--' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="isOk(detail) ? 'success' : 'danger'">{{ isOk(detail) ? '成功' : '失败' }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="detail.summary" class="detail-section">
        <div class="section-title">分析摘要</div>
        <div class="section-body">{{ detail.summary }}</div>
      </div>

      <div class="detail-section">
        <div class="section-title">市场影响</div>
        <div v-for="m in detailMarkets" :key="m.name" class="market-block">
          <div class="market-line">
            <span>{{ m.name }}</span>
            <el-tag v-if="m.direction" size="small" effect="dark" :color="directionColor(m.direction)" class="dir-tag">
              {{ directionLabel(m.direction) }} {{ scoreText(m.score) }}分
            </el-tag>
            <span v-else class="muted">暂无</span>
          </div>
          <p v-if="m.reason" class="reason">{{ m.reason }}</p>
        </div>
      </div>

      <div v-if="riskEvents.length" class="detail-section">
        <div class="section-title">风险事件</div>
        <div v-for="(item, i) in riskEvents" :key="i" class="risk-item">{{ item }}</div>
      </div>

      <div v-if="detail.errorMsg" class="detail-section">
        <div class="section-title error">错误信息</div>
        <div class="section-body error-body">{{ detail.errorMsg }}</div>
      </div>

      <template #footer>
        <el-button @click="open = false">关 闭</el-button>
      </template>
    </el-dialog>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { getAnalysis, listAnalysis, runAnalysis } from '@/api/sentiment'
import { score100 } from '@/utils/format'
import { unwrap, unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const analyzing = ref(false)
const list = ref([])
const page = ref(1)
const total = ref(0)
const dateRange = ref([])
const open = ref(false)
const detail = ref({})
const query = ref({ status: undefined })

function scoreText(v) {
  const n = score100(v)
  return n == null ? '--' : String(n)
}

function formatTime(v) {
  const s = String(v || '').replace('T', ' ').trim()
  return s ? s.slice(0, 19) : ''
}

function isOk(row) {
  return String(row?.status) === '0'
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
  if (d === 'up') return '#f56c6c'
  if (d === 'down') return '#67c23a'
  return '#909399'
}

function directionLabel(direction) {
  const d = normalizeDirection(direction)
  if (d === 'up') return '利多'
  if (d === 'down') return '利空'
  return '中性'
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

const detailMarkets = computed(() => [
  { name: '美股三大指数', direction: detail.value.usDirection, score: detail.value.usScore, reason: detail.value.usReason },
  { name: '港股指数', direction: detail.value.hkDirection, score: detail.value.hkScore, reason: detail.value.hkReason },
  { name: 'A股指数', direction: detail.value.aDirection, score: detail.value.aScore, reason: detail.value.aReason }
])

const riskEvents = computed(() => parseRisk(detail.value.riskEvents))

function dateParams() {
  const [begin, end] = dateRange.value || []
  if (!begin || !end) return {}
  return { beginTime: String(begin).slice(0, 10), endTime: String(end).slice(0, 10) }
}

async function load() {
  loading.value = true
  try {
    const res = await listAnalysis({
      pageNum: page.value,
      pageSize: 20,
      status: query.value.status || undefined,
      ...dateParams()
    })
    list.value = unwrapList(res)
    total.value = unwrapTotal(res, list.value.length)
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  query.value = { status: undefined }
  dateRange.value = []
  search()
}

async function openDetail(row) {
  if (!row) return
  try {
    const res = await getAnalysis(row.analysisId)
    detail.value = unwrap(res) || row
  } catch {
    detail.value = row
  }
  open.value = true
}

async function analyze() {
  analyzing.value = true
  try {
    const res = await runAnalysis()
    const d = unwrap(res)
    ElMessage.success(res?.msg || (d.accepted ? '已加入后台队列' : 'AI分析任务已触发'))
    if (!d.accepted) load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sentiment-page :deep(.page-hero) {
  padding: 12px 14px !important;
}
.filter-card {
  padding: 8px 10px !important;
}
.compact-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}
.compact-form :deep(.el-form-item) {
  margin-bottom: 0 !important;
  margin-right: 8px;
}
.dir-tag {
  border: none;
  color: #fff;
}
.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
.detail-section {
  margin-top: 14px;
}
.section-title {
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid var(--accent);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-emphasis);
}
.section-title.error {
  border-left-color: var(--danger);
}
.section-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  white-space: pre-wrap;
}
.error-body {
  color: var(--danger);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-radius: 6px;
  padding: 8px 10px;
}
.market-block {
  margin-bottom: 10px;
}
.market-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-emphasis);
}
.reason {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}
.muted {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 400;
}
.risk-item {
  padding: 8px 10px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--warning) 12%, transparent);
  color: var(--warning);
  font-size: 13px;
  line-height: 1.5;
}
:deep(.el-empty) {
  padding: 8px 0;
  min-height: 0;
}
:deep(.el-empty__image) {
  width: 48px;
}
:deep(.el-table) {
  font-size: 13px;
}
:deep(.el-table th.el-table__cell),
:deep(.el-table td.el-table__cell) {
  padding: 6px 0;
  height: 34px;
}
</style>
