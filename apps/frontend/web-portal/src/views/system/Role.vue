<template>
  <PageFrame title="角色管理" badge="「角色管理 /system/role」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无角色">
        <el-table-column prop="roleId" label="ID" width="80" />
        <el-table-column prop="roleName" label="名称" min-width="140" />
        <el-table-column prop="roleKey" label="权限" min-width="140" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column prop="createTime" label="创建" width="170" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listRole } from '@/api/system'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await listRole({ pageNum: 1, pageSize: 50 }))
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
