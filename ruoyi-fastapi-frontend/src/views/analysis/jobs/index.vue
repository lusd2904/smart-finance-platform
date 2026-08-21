<template>
  <div class="app-container jobs-page">
    <div class="page-hero">
      <div>
        <h2>自动分析任务</h2>
        <p>行情同步、自选研判、舆情 AI、因子日扫等定时任务由独立 sentiment-jobs 执行，不占用平台 API 进程。</p>
      </div>
      <div class="hero-actions">
        <el-tag :type="alive ? 'success' : 'danger'" effect="dark" class="alive-tag">
          {{ alive ? 'jobs 在线' : 'jobs 离线' }}
        </el-tag>
        <el-button icon="Refresh" :loading="loading" @click="loadOverview">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="!alive"
      class="mb16"
      type="error"
      show-icon
      :closable="false"
      title="sentiment-jobs 未在线"
      description="平台 API 不会在本进程内执行这些任务。请启动 sentiment-jobs 容器后再启用或立即执行。"
    />

    <el-row :gutter="16" class="mb16">
      <el-col :xs="12" :sm="8" :md="4" v-for="card in statCards" :key="card.label">
        <div class="stat-card" :class="card.tone">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel mb16">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">调度实例</span>
          <span class="panel-sub">{{ overview.heartbeatAt || '尚无心跳' }}</span>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="Worker">{{ overview.workerId || '--' }}</el-descriptions-item>
        <el-descriptions-item label="主机">{{ overview.hostname || '--' }}</el-descriptions-item>
        <el-descriptions-item label="PID">{{ overview.pid || '--' }}</el-descriptions-item>
        <el-descriptions-item label="队列深度">{{ overview.queueDepth ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="正在执行">{{ runningText }}</el-descriptions-item>
        <el-descriptions-item label="API 角色">{{ overview.appRole || '--' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="panel" v-loading="loading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">任务清单</span>
          <el-radio-group v-model="category" size="small">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="market">行情</el-radio-button>
            <el-radio-button label="quant">量化</el-radio-button>
            <el-radio-button label="sentiment">舆情</el-radio-button>
            <el-radio-button label="trade">交易</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <el-empty v-if="!filteredJobs.length && !loading" description="没有匹配的自动分析任务" :image-size="72" />

      <div class="job-grid">
        <div v-for="job in filteredJobs" :key="job.jobId" class="job-card">
          <div class="job-top">
            <div>
              <div class="job-title">{{ job.title }}</div>
              <div class="job-meta">
                <el-tag size="small" :type="categoryType(job.category)" effect="plain">{{ job.categoryLabel }}</el-tag>
                <el-tag v-if="job.heavy" size="small" type="warning" effect="plain">重任务</el-tag>
                <el-tag v-if="!job.registered" size="small" type="info" effect="plain">未注册</el-tag>
              </div>
            </div>
            <el-switch
              :model-value="job.status === '0'"
              :disabled="!job.registered"
              :loading="statusLoading === job.jobId"
              @change="(val) => handleStatus(job, val)"
              v-hasPermi="['analysis:job:edit']"
            />
          </div>
          <p class="job-desc">{{ job.description }}</p>
          <div class="job-stats">
            <div>
              <span class="k">调度</span>
              <span class="v">{{ job.scheduleLabel }}</span>
            </div>
            <div>
              <span class="k">上次</span>
              <span class="v" :class="runClass(job.lastRunStatus)">{{ lastRunText(job) }}</span>
            </div>
            <div>
              <span class="k">下次</span>
              <span class="v">{{ job.nextRunTime || (job.status === '0' ? '等待心跳' : '已暂停') }}</span>
            </div>
          </div>
          <div class="job-actions">
            <el-button
              type="primary"
              link
              :disabled="!job.registered"
              :loading="runLoading === job.jobId"
              @click="handleRun(job)"
              v-hasPermi="['analysis:job:run']"
            >立即执行</el-button>
            <el-button type="primary" link @click="openLogs(job)" v-hasPermi="['analysis:job:query']">执行日志</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-drawer v-model="logOpen" :title="logJob ? `${logJob.title} · 执行日志` : '执行日志'" size="42%">
      <el-table v-loading="logLoading" :data="logs" size="small" max-height="560">
        <el-table-column prop="createTime" label="时间" width="170" />
        <el-table-column label="结果" width="80" align="center">
          <template #default="scope">
            <el-tag size="small" :type="scope.row.status === '0' ? 'success' : 'danger'">
              {{ scope.row.status === '0' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="jobMessage" label="信息" min-width="220" show-overflow-tooltip />
        <el-table-column prop="exceptionInfo" label="异常" min-width="160" show-overflow-tooltip />
      </el-table>
      <pagination
        v-show="logTotal > 0"
        :total="logTotal"
        v-model:page="logQuery.pageNum"
        v-model:limit="logQuery.pageSize"
        @pagination="loadLogs"
      />
    </el-drawer>
  </div>
</template>

<script setup name="AnalysisJobsIndex">
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { changeAnalysisJobStatus, getAnalysisOverview, listAnalysisJobLogs, runAnalysisJob } from '@/api/analysis/scheduler'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const overview = ref({})
const category = ref('all')
const statusLoading = ref(null)
const runLoading = ref(null)
const logOpen = ref(false)
const logJob = ref(null)
const logs = ref([])
const logTotal = ref(0)
const logLoading = ref(false)
const logQuery = reactive({ pageNum: 1, pageSize: 20 })
let timer = null

const alive = computed(() => Boolean(overview.value.schedulerAlive))
const jobs = computed(() => overview.value.jobs || [])
const filteredJobs = computed(() => {
  if (category.value === 'all') return jobs.value
  return jobs.value.filter((item) => item.category === category.value)
})
const runningText = computed(() => {
  const items = overview.value.running || []
  if (!items.length) return '空闲'
  return items.map((item) => item.type || item).join('、')
})
const statCards = computed(() => [
  { label: '已启用', value: overview.value.enabledCount ?? 0, tone: 't-green' },
  { label: '已暂停', value: overview.value.pausedCount ?? 0, tone: 't-gray' },
  { label: '队列深度', value: overview.value.queueDepth ?? 0, tone: 't-blue' },
  { label: '今日成功', value: overview.value.todaySuccess ?? 0, tone: 't-green' },
  { label: '今日失败', value: overview.value.todayFailed ?? 0, tone: 't-red' },
  { label: '未注册', value: overview.value.missingCount ?? 0, tone: 't-gray' }
])

function categoryType(value) {
  return { market: 'warning', quant: 'success', sentiment: '', trade: 'danger' }[value] || 'info'
}

function runClass(status) {
  if (status === '0') return 'ok'
  if (status === '1') return 'bad'
  return ''
}

function lastRunText(job) {
  if (!job.lastRunTime) return '尚未运行'
  const flag = job.lastRunStatus === '1' ? '失败' : '成功'
  return `${job.lastRunTime} · ${flag}`
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await getAnalysisOverview()
    overview.value = res.data || {}
  } finally {
    loading.value = false
  }
}

async function loadOverviewQuiet() {
  try {
    const res = await getAnalysisOverview()
    overview.value = res.data || {}
  } catch {
    /* ignore poll errors */
  }
}

async function handleStatus(job, enabled) {
  const status = enabled ? '0' : '1'
  statusLoading.value = job.jobId
  try {
    await changeAnalysisJobStatus(job.jobId, status)
    proxy.$modal.msgSuccess(enabled ? '已启用，调度微服务将同步' : '已暂停')
    await loadOverview()
  } catch {
    /* request util already toasts */
  } finally {
    statusLoading.value = null
  }
}

async function handleRun(job) {
  runLoading.value = job.jobId
  try {
    const res = await runAnalysisJob(job.jobId)
    proxy.$modal.msgSuccess(res.msg || '已提交执行')
    await loadOverview()
  } finally {
    runLoading.value = null
  }
}

async function openLogs(job) {
  logJob.value = job
  logQuery.pageNum = 1
  logOpen.value = true
  await loadLogs()
}

async function loadLogs() {
  if (!logJob.value) return
  logLoading.value = true
  try {
    const res = await listAnalysisJobLogs(logJob.value.jobId, logQuery)
    logs.value = res.rows || []
    logTotal.value = res.total || 0
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  loadOverview()
  timer = setInterval(loadOverviewQuiet, 10000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.page-hero {
  display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; max-width: 720px; }
}
.hero-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.alive-tag { height: 28px; line-height: 28px; }
.mb16 { margin-bottom: 16px; }
.stat-card {
  border-radius: 14px; padding: 14px 16px; color: #fff; margin-bottom: 12px;
  .stat-label { font-size: 12px; opacity: 0.85; }
  .stat-value { font-size: 24px; font-weight: 700; margin-top: 4px; }
  &.t-blue { background: linear-gradient(135deg, #6366f1, #8b5cf6); }
  &.t-green { background: linear-gradient(135deg, #10b981, #34d399); }
  &.t-red { background: linear-gradient(135deg, #ef4444, #f87171); }
  &.t-gray { background: linear-gradient(135deg, #64748b, #94a3b8); }
}
.panel { border-radius: 14px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.panel-title { font-weight: 600; }
.panel-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.job-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}
.job-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 14px 16px;
  background: var(--el-bg-color);
}
.job-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.job-title { font-weight: 600; margin-bottom: 6px; }
.job-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.job-desc { margin: 10px 0 12px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; min-height: 40px; }
.job-stats {
  display: grid; grid-template-columns: 1fr; gap: 6px; font-size: 12px;
  .k { color: var(--el-text-color-secondary); margin-right: 8px; }
  .v { color: var(--el-text-color-primary); }
  .ok { color: #10b981; }
  .bad { color: #ef4444; }
}
.job-actions { display: flex; gap: 8px; margin-top: 10px; }
</style>
