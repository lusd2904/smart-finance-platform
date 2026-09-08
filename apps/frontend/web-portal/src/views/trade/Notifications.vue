<template>
  <PageFrame title="通知中心" :loading="loading">
    <template #actions>
      <el-button type="primary" @click="markAll">全部已读</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-empty v-if="!loading && !list.length" description="暂无通知" />
    <article v-for="n in list" :key="n.id" class="news-line glass-panel">
      <div>
        <strong>{{ n.title || n.type || '通知' }}</strong>
        <el-tag v-if="n.read || n.isRead" size="small">已读</el-tag>
      </div>
      <p>{{ n.content || n.message || '' }}</p>
      <span class="muted">{{ n.createdAt || n.time || '' }}</span>
    </article>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { listNotifications, readNotifications } from '@/api/trade'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await listNotifications())
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function markAll() {
  try {
    await readNotifications()
    ElMessage.success('已读')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '失败')
  }
}

onMounted(load)
</script>

<style scoped>
.muted { color: var(--text-secondary); font-size: 12px; }
p { margin: 0; }
</style>
