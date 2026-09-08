<template>
  <PageFrame title="模型管理" badge="「模型管理 /ai/model」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无模型">
        <el-table-column prop="modelName" label="名称" min-width="140" />
        <el-table-column prop="provider" label="厂商" width="110" />
        <el-table-column prop="modelKey" label="模型" min-width="140" />
        <el-table-column prop="scope" label="范围" width="110" />
        <el-table-column label="默认" width="80">
          <template #default="{ row }">{{ row.isDefault ? '是' : '' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listModel } from '@/api/ai'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await listModel({ pageNum: 1, pageSize: 50 }))
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
