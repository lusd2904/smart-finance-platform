<template>
  <PageFrame title="分析历史" badge="「分析历史 /sentiment/analysis」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无分析">
        <el-table-column prop="createdAt" label="时间" width="170" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="direction" label="方向" width="90" />
        <el-table-column prop="score" label="分数" width="80" align="right" />
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" @current-change="load" />
      </div>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listAnalysis } from '@/api/sentiment'
import { unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const list = ref([])
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await listAnalysis({ pageNum: page.value, pageSize: 20 })
    list.value = unwrapList(res)
    total.value = unwrapTotal(res, list.value.length)
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pager { display: flex; justify-content: flex-end; padding-top: 10px; }
</style>
