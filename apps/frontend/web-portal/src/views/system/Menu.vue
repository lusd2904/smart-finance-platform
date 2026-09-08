<template>
  <PageFrame title="菜单管理" badge="「菜单管理 /system/menu」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe row-key="menuId" empty-text="暂无菜单">
        <el-table-column prop="menuName" label="名称" min-width="180" />
        <el-table-column prop="orderNum" label="排序" width="70" />
        <el-table-column prop="path" label="路径" min-width="160" />
        <el-table-column prop="component" label="组件" min-width="160" />
        <el-table-column prop="perms" label="权限" min-width="160" />
        <el-table-column prop="status" label="状态" width="80" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listMenu } from '@/api/system'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await listMenu({}))
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
