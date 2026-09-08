<template>
  <PageFrame title="研判工作台" badge="「研判工作台 /ai/chat」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="sending" @click="send">研判</el-button>
    </template>
    <el-row :gutter="12">
      <el-col :xs="24" :lg="8">
        <el-card shadow="never" class="glass-panel">
          <template #header><h3>会话</h3></template>
          <el-empty v-if="!sessions.length" description="暂无会话" :image-size="48" />
          <div v-for="s in sessions" :key="s.sessionId || s.id" class="news-line" @click="open(s)">
            <strong>{{ s.title || s.sessionId }}</strong>
            <span class="muted">{{ s.updatedAt || '' }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" class="glass-panel">
          <el-input v-model="prompt" type="textarea" :rows="4" placeholder="标的 / 问题" />
          <div v-if="answer" class="answer">{{ answer }}</div>
        </el-card>
      </el-col>
    </el-row>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { analyzeOneshot, getChatSession, listChatSession } from '@/api/ai'
import { unwrap, unwrapList } from '@/utils/list'

const route = useRoute()
const loading = ref(false)
const sending = ref(false)
const sessions = ref([])
const prompt = ref('')
const answer = ref('')

async function load() {
  loading.value = true
  try {
    sessions.value = unwrapList(await listChatSession())
  } catch {
    sessions.value = []
  } finally {
    loading.value = false
  }
}

async function open(s) {
  try {
    const data = unwrap(await getChatSession(s.sessionId || s.id))
    answer.value = data.answer || data.content || (data.messages || []).map((m) => m.content).join('\n') || ''
  } catch (e) {
    ElMessage.error(e?.message || '加载失败')
  }
}

async function send() {
  if (!prompt.value.trim()) return
  sending.value = true
  try {
    const data = unwrap(await analyzeOneshot({ prompt: prompt.value }))
    answer.value = data.answer || data.content || data.summary || JSON.stringify(data)
  } catch (e) {
    ElMessage.error(e?.message || '研判失败')
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  const symbol = String(route.query.symbol || '').trim()
  if (symbol) prompt.value = `${symbol} ${route.query.market || ''} 研判`.trim()
  load()
})
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.answer { margin-top: 12px; white-space: pre-wrap; color: var(--text-primary); }
.news-line { cursor: pointer; margin-bottom: 8px; }
</style>
