<template>
  <PageFrame title="自动分析" subtitle="调度总览 · 启停 · 立即执行" badge="「自动分析 /analysis/jobs」" :loading="loading">
    <template #actions>
      <el-tag :type="alive ? 'success' : 'info'">{{ alive ? '在线' : '离线' }}</el-tag>
      <el-radio-group v-model="category" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="market">行情</el-radio-button>
        <el-radio-button value="quant">量化</el-radio-button>
        <el-radio-button value="sentiment">舆情</el-radio-button>
        <el-radio-button value="trade">交易</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>任务</span><strong>{{ jobs.length }}</strong></article>
      <article class="stat-tile glass-panel"><span>启用</span><strong>{{ jobs.filter((j) => j.status === '0').length }}</strong></article>
      <article class="stat-tile glass-panel"><span>队列</span><strong>{{ overview.queueDepth ?? 0 }}</strong></article>
      <article class="stat-tile glass-panel"><span>Worker</span><strong>{{ overview.workerId || '--' }}</strong></article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无任务">
        <el-table-column prop="title" label="任务" min-width="180" />
        <el-table-column prop="categoryLabel" label="分类" width="90">
          <template #default="{ row }">{{ row.categoryLabel || row.category }}</template>
        </el-table-column>
        <el-table-column prop="cron" label="Cron" min-width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch :model-value="row.status === '0'" @change="(on) => toggle(row, on)" />
          </template>
        </el-table-column>
        <el-table-column width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click="run(row)">执行</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { changeAnalysisJobStatus, getAnalysisOverview, runAnalysisJob } from '@/api/analysis'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const category = ref('all')
const overview = ref({})
const jobs = ref([])
const alive = computed(() => Boolean(overview.value.alive ?? overview.value.online ?? overview.value.workerId))

const filtered = computed(() => {
  if (category.value === 'all') return jobs.value
  return jobs.value.filter((j) => j.category === category.value)
})

async function load() {
  loading.value = true
  try {
    const res = await getAnalysisOverview()
    const data = unwrap(res)
    overview.value = data
    jobs.value = data.jobs || unwrapList(res)
  } catch {
    overview.value = {}
    jobs.value = []
  } finally {
    loading.value = false
  }
}

async function toggle(row, on) {
  try {
    await changeAnalysisJobStatus(row.jobId || row.id, on ? '0' : '1')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  }
}

async function run(row) {
  try {
    await runAnalysisJob(row.jobId || row.id)
    ElMessage.success('已执行')
  } catch (e) {
    ElMessage.error(e?.message || '执行失败')
  }
}

onMounted(load)
</script>
