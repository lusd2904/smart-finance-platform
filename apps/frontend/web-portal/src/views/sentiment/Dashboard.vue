<template>
  <PageFrame title="舆情大盘" subtitle="采集 · 分析 · 最近研判" badge="「舆情大盘 /sentiment/dashboard」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="collecting" @click="collect">采集</el-button>
      <el-button :loading="analyzing" @click="analyze">分析</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>
    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>资讯</span><strong>{{ stats.total ?? stats.newsCount ?? 0 }}</strong></article>
      <article class="stat-tile glass-panel"><span>今日</span><strong>{{ stats.today ?? stats.todayCount ?? 0 }}</strong></article>
      <article class="stat-tile glass-panel"><span>分析</span><strong>{{ stats.analysisCount ?? history.length }}</strong></article>
      <article class="stat-tile glass-panel"><span>最新</span><strong>{{ latestTime || '--' }}</strong></article>
    </div>
    <el-card shadow="never" class="glass-panel">
      <template #header><h3>最近分析</h3></template>
      <el-table :data="history" stripe empty-text="暂无分析">
        <el-table-column prop="createdAt" label="时间" width="170" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="direction" label="方向" width="90" />
        <el-table-column prop="score" label="分数" width="80" align="right" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { collectNews, getStats, listAnalysis, runAnalysis } from '@/api/sentiment'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const collecting = ref(false)
const analyzing = ref(false)
const stats = ref({})
const history = ref([])
const latestTime = ref('')

async function load() {
  loading.value = true
  try {
    const [s, a] = await Promise.allSettled([getStats(), listAnalysis({ pageNum: 1, pageSize: 20 })])
    if (s.status === 'fulfilled') stats.value = unwrap(s.value)
    if (a.status === 'fulfilled') {
      history.value = unwrapList(a.value)
      latestTime.value = history.value[0]?.createdAt || history.value[0]?.analyzeTime || ''
    }
  } finally {
    loading.value = false
  }
}

async function collect() {
  collecting.value = true
  try {
    await collectNews()
    ElMessage.success('已采集')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '采集失败')
  } finally {
    collecting.value = false
  }
}

async function analyze() {
  analyzing.value = true
  try {
    await runAnalysis()
    ElMessage.success('已分析')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
</style>
