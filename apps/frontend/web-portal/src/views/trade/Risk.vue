<template>
  <PageFrame title="风控" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="evaluating" @click="runEval">评估</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>
    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>规则</span><strong>{{ rules.length }}</strong></article>
      <article class="stat-tile glass-panel"><span>事件</span><strong>{{ events.length }}</strong></article>
      <article class="stat-tile glass-panel"><span>净值</span><strong>{{ sheet.netAssets ?? sheet.equity ?? '--' }}</strong></article>
      <article class="stat-tile glass-panel"><span>回撤</span><strong :class="changeClass(-(sheet.maxDrawdown || 0))">{{ sheet.maxDrawdown ?? '--' }}</strong></article>
    </div>
    <el-card shadow="never" class="glass-panel">
      <template #header><h3>规则</h3></template>
      <el-table :data="rules" stripe empty-text="暂无规则">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="threshold" label="阈值" width="100" />
        <el-table-column prop="enabled" label="启用" width="80" />
      </el-table>
    </el-card>
    <el-card shadow="never" class="glass-panel">
      <template #header><h3>事件</h3></template>
      <el-table :data="events" stripe empty-text="暂无事件">
        <el-table-column prop="createdAt" label="时间" width="160" />
        <el-table-column prop="ruleName" label="规则" min-width="140" />
        <el-table-column prop="message" label="说明" min-width="180" />
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { evaluateRisk, getRiskTearsheet, listRiskEvents, listRiskRules } from '@/api/trade'
import { changeClass } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const evaluating = ref(false)
const rules = ref([])
const events = ref([])
const sheet = ref({})

async function load() {
  loading.value = true
  try {
    const [r, e, t] = await Promise.allSettled([listRiskRules(), listRiskEvents(), getRiskTearsheet()])
    if (r.status === 'fulfilled') rules.value = unwrapList(r.value)
    if (e.status === 'fulfilled') events.value = unwrapList(e.value)
    if (t.status === 'fulfilled') sheet.value = unwrap(t.value)
  } finally {
    loading.value = false
  }
}

async function runEval() {
  evaluating.value = true
  try {
    await evaluateRisk()
    ElMessage.success('已评估')
    load()
  } catch (err) {
    ElMessage.error(err?.message || '评估失败')
  } finally {
    evaluating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
</style>
