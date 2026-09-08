<template>
  <PageFrame title="通知中心" :loading="loading">
    <template #actions>
      <el-button @click="markAll">全部已读</el-button>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-timeline v-if="list.length">
        <el-timeline-item v-for="n in list" :key="n.id" :type="typeMap[n.level] || 'primary'" :timestamp="n.createTime" placement="top">
          <div class="n-title" :class="{ unread: !n.read }">
            {{ n.title }}
            <el-tag size="small" effect="plain">{{ n.category }}</el-tag>
          </div>
          <div class="n-body">{{ n.content }}</div>
          <el-button v-if="!n.read" link type="primary" @click="mark(n)">标为已读</el-button>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无通知" :image-size="72" />
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listNotifications, readNotifications } from '@/api/trade'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])
const typeMap = { success: 'success', danger: 'danger', warning: 'warning', info: 'primary' }

async function load() {
  loading.value = true
  try {
    const res = await listNotifications(80)
    list.value = Array.isArray(res.data) ? res.data : unwrapList(res)
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function mark(n) {
  await readNotifications(n.id)
  n.read = true
}

async function markAll() {
  await readNotifications()
  list.value = list.value.map((n) => ({ ...n, read: true }))
}

onMounted(load)
</script>

<style scoped>
.n-title { font-weight: 600; color: var(--text-emphasis); margin-bottom: 4px; display: flex; gap: 8px; align-items: center; }
.n-title.unread { color: var(--accent); }
.n-body { color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
</style>
