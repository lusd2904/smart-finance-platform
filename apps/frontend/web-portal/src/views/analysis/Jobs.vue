<template>
  <PageFrame
    title="任务中心"
    subtitle="Cron · 上次运行 · 重试 · 手动触发"
    :loading="loading"
  >
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="搜索任务名" style="width:180px" :prefix-icon="Search" />
      <el-radio-group v-model="filter">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="running">运行中</el-radio-button>
        <el-radio-button value="failed">失败</el-radio-button>
        <el-radio-button value="idle">空闲</el-radio-button>
      </el-radio-group>
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-button type="primary" @click="ElMessage.info('新建任务待后端字段对齐')">+ 新建任务</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · GET /analysis/scheduler/overview · 侧栏 menus.js 已挂" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <div class="stat-strip">
      <article class="stat-tile glass-panel">
        <span>任务总数</span>
        <strong class="numeric">{{ kpis.total }}</strong>
        <small>已启用 {{ kpis.enabled }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>运行中</span>
        <strong class="numeric">{{ kpis.running }}</strong>
        <small>{{ kpis.runningHint }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>今日成功</span>
        <strong class="numeric">{{ kpis.success }}</strong>
        <small>失败 {{ kpis.failed }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>待重试</span>
        <strong class="numeric">{{ kpis.retry }}</strong>
        <small>{{ kpis.retryHint }}</small>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无任务">
        <el-table-column type="index" label="#" width="52" />
        <el-table-column label="名称" min-width="180">
          <template #default="{ row }">{{ jobTitle(row) }}</template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch :model-value="isOn(row)" @change="(on) => toggle(row, on)" />
          </template>
        </el-table-column>
        <el-table-column label="Cron" min-width="140">
          <template #default="{ row }"><span class="numeric">{{ cronText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="上次运行" width="170">
          <template #default="{ row }"><span class="numeric">{{ row.lastRunAt || row.lastRun || row.updateTime || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="重试" width="72" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.retryCount ?? row.retry ?? 0 }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="run(row)">触发</el-button>
            <el-button link type="primary" @click="openLogs(row)">日志</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="logOpen" :title="logTitle" size="420px">
      <el-empty v-if="!logs.length" description="日志抽屉占位 · 待任务字段对齐" :image-size="64" />
      <article v-for="(line, i) in logs" :key="i" class="job-card">
        <strong class="numeric">{{ line.time || line.createdAt || '' }}</strong>
        <p>{{ line.message || line.msg || line }}</p>
      </article>
    </el-drawer>

    <template #legend>
      <span>薄壳 · 启用开关 · 手动触发 · 日志抽屉占位 · path /analysis/jobs 稳定</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { changeAnalysisJobStatus, getAnalysisOverview, listAnalysisJobLogs, runAnalysisJob } from '@/api/analysis'
import { unwrap, unwrapList } from '@/utils/list'
import { useUserStore } from '@/store/user'
import { errorText, isDemoSession, stubJobs } from '@/utils/stubs'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const loading = ref(false)
const usingStub = ref(false)
const loadError = ref('')
const keyword = ref('')
const filter = ref('all')
const overview = ref({})
const jobs = ref([])
const logOpen = ref(false)
const logTitle = ref('日志')
const logs = ref([])

function isOn(row) {
  return row.status === '0' || row.enabled === true
}
function runState(row) {
  const raw = String(row.runState || row.state || row.lastStatus || '').toLowerCase()
  if (row.running === true || raw === 'running' || raw === '运行中') return 'running'
  if (raw.includes('fail') || raw.includes('失败') || row.lastError) return 'failed'
  return 'idle'
}
function jobTitle(row) {
  return row.title || row.name || row.jobName || '任务'
}
function cronText(row) {
  const cron = String(row.cron || '').trim()
  return !cron || cron === '-' ? '手动' : cron
}

const kpis = computed(() => {
  const list = jobs.value
  const running = list.filter((j) => runState(j) === 'running')
  const failed = list.filter((j) => runState(j) === 'failed')
  const retryRows = list.filter((j) => Number(j.retryCount || j.retry) > 0 || runState(j) === 'failed')
  return {
    total: list.length,
    enabled: list.filter((j) => isOn(j)).length,
    running: running.length,
    runningHint: running[0] ? jobTitle(running[0]) : '无',
    success: overview.value.todaySuccess ?? overview.value.success24h ?? list.filter((j) => j.lastOk).length,
    failed: overview.value.todayFail ?? failed.length,
    retry: overview.value.retryPending ?? retryRows.length,
    retryHint: retryRows[0] ? jobTitle(retryRows[0]) : '无'
  }
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return jobs.value.filter((j) => {
    const stateOk = filter.value === 'all' || runState(j) === filter.value
    const text = `${j.title || ''} ${j.name || ''} ${j.jobName || ''} ${j.cron || ''}`.toLowerCase()
    return stateOk && (!kw || text.includes(kw))
  })
})

async function load() {
  if (demoMode()) {
    applyStub()
    return
  }
  loading.value = true
  usingStub.value = false
  loadError.value = ''
  try {
    const res = await getAnalysisOverview()
    const data = unwrap(res)
    overview.value = data
    jobs.value = data.jobs || unwrapList(res)
  } catch (e) {
    overview.value = {}
    jobs.value = []
    loadError.value = errorText(e, '任务加载失败')
  } finally {
    loading.value = false
  }
}

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  loadError.value = ''
  overview.value = { todaySuccess: 46, todayFail: 2, retryPending: 1 }
  jobs.value = stubJobs()
}

async function toggle(row, on) {
  try {
    await changeAnalysisJobStatus(row.jobId || row.id, on ? '0' : '1')
    await load()
  } catch (e) {
    if (usingStub.value) {
      row.status = on ? '0' : '1'
      ElMessage.success('已更新（STUB）')
    } else ElMessage.error(e?.message || '更新失败')
  }
}

async function run(row) {
  try {
    await runAnalysisJob(row.jobId || row.id)
    ElMessage.success('已触发')
    load()
  } catch (e) {
    ElMessage[usingStub.value ? 'success' : 'error'](usingStub.value ? '已触发（STUB）' : (e?.message || '执行失败'))
  }
}

async function openLogs(row) {
  logTitle.value = `${row.title || row.name || '任务'} · 日志`
  logOpen.value = true
  logs.value = []
  try {
    const res = await listAnalysisJobLogs(row.jobId || row.id, { limit: 30 })
    logs.value = unwrapList(res) || unwrap(res).logs || []
  } catch {
    logs.value = row.lastError ? [{ time: row.lastRunAt, message: row.lastError }] : []
  }
}

onMounted(load)
</script>

<style scoped>
.stat-tile small {
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
