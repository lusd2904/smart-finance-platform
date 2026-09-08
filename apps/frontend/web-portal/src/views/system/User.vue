<template>
  <PageFrame title="用户管理" badge="「用户管理 /system/user」" :loading="loading">
    <template #actions>
      <el-input v-model="userName" clearable placeholder="账号" style="width:140px" @keyup.enter="load" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无用户">
        <el-table-column prop="userId" label="ID" width="80" />
        <el-table-column prop="userName" label="账号" width="140" />
        <el-table-column prop="nickName" label="昵称" min-width="120" />
        <el-table-column prop="phonenumber" label="手机" width="130" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column prop="createTime" label="创建" width="170" />
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
import { listUser } from '@/api/system'
import { unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const userName = ref('')
const list = ref([])
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await listUser({ pageNum: page.value, pageSize: 20, userName: userName.value || undefined })
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
