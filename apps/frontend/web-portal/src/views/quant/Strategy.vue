<template>
  <PageFrame title="策略信号" subtitle="扫描历史 · 立即运行" badge="「策略信号 /quant/strategy」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="running" @click="run">运行</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无信号">
        <el-table-column prop="createdAt" label="时间" width="170" />
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="signal" label="信号" width="90" />
        <el-table-column prop="score" label="得分" width="80" align="right" />
        <el-table-column prop="profile" label="配置" width="100" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { listStrategyHistory, runStrategy } from '@/api/quant'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const running = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await listStrategyHistory({ pageNum: 1, pageSize: 50 }))
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function run() {
  running.value = true
  try {
    await runStrategy({})
    ElMessage.success('已运行')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '运行失败')
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>
