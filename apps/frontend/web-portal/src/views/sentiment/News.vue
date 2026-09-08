<template>
  <PageFrame title="资讯列表" badge="「资讯列表 /sentiment/news」" :loading="loading">
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="标题" style="width:180px" @keyup.enter="load" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无资讯">
        <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="sentiment" label="情绪" width="80" />
        <el-table-column prop="publishedAt" label="时间" width="170" />
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
import { listNews } from '@/api/sentiment'
import { unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const keyword = ref('')
const list = ref([])
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await listNews({ pageNum: page.value, pageSize: 20, title: keyword.value || undefined })
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
