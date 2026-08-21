<template>
  <div class="app-container req-chat">
    <el-container class="shell">
      <el-aside width="240px" class="side">
        <div class="side-title">需求沟通</div>
        <div class="side-sub">不含 admin / niangao · 固定 Grok</div>
        <div class="member" v-for="m in members" :key="m.userId + m.role">
          <el-avatar :size="28" :class="m.role === 'ai' ? 'ai' : 'user'">{{ (m.nickName || '?').slice(0, 1) }}</el-avatar>
          <div>
            <div class="m-name">{{ m.nickName }}</div>
            <div class="m-role">{{ m.role === 'ai' ? 'Grok' : m.userName }}</div>
          </div>
        </div>
      </el-aside>
      <el-main class="main">
        <div class="toolbar">
          <span>讨论可行性，确定后让 Grok 写入需求清单</span>
          <div>
            <el-button type="success" :loading="summarizing" @click="handleSummarize" v-hasPermi="['ai:req:chat']">总结并写入清单</el-button>
            <el-button @click="$router.push('/ai/req-list')">打开需求清单</el-button>
          </div>
        </div>
        <div ref="listRef" class="msgs" v-loading="loading">
          <div v-for="msg in messages" :key="msg.msgId" :class="['row', msg.role]">
            <div class="bubble">
              <div class="who">{{ msg.nickName }} <span>{{ msg.createTime }}</span></div>
              <div class="body">{{ msg.content }}</div>
            </div>
          </div>
          <el-empty v-if="!messages.length && !loading" description="还没有消息，先说明要做的需求" />
        </div>
        <div class="composer">
          <el-input
            v-model="draft"
            type="textarea"
            :rows="3"
            placeholder="输入需求讨论。确定后可点「总结并写入清单」，或在对话里说「确定需求，写入清单」。"
            @keydown.enter.exact.prevent="handleSend"
          />
          <el-button type="primary" :loading="sending" :disabled="!draft.trim()" @click="handleSend">发送</el-button>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup name="AiReqChat">
import { getReqRoom, getReqMessages, sendReqMessage, summarizeReq } from '@/api/ai/req'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const sending = ref(false)
const summarizing = ref(false)
const members = ref([])
const messages = ref([])
const draft = ref('')
const listRef = ref()
let timer = null

function scrollBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadRoom() {
  const res = await getReqRoom()
  members.value = (res.data && res.data.members) || []
}

async function loadMessages(silent) {
  if (!silent) loading.value = true
  try {
    const res = await getReqMessages({ limit: 200 })
    messages.value = (res.data && res.data.items) || []
    scrollBottom()
  } finally {
    if (!silent) loading.value = false
  }
}

async function handleSend() {
  const content = draft.value.trim()
  if (!content || sending.value) return
  draft.value = ''
  await nextTick()
  sending.value = true
  try {
    const res = await sendReqMessage({ content })
    const data = res.data || {}
    if (data.userMessage) messages.value.push(data.userMessage)
    if (data.aiMessage) messages.value.push(data.aiMessage)
    scrollBottom()
    if ((data.requirements || []).length) {
      proxy.$modal.msgSuccess(`已写入 ${(data.requirements || []).length} 条需求`)
    }
  } catch (e) {
    if (!draft.value.trim()) draft.value = content
    throw e
  } finally {
    sending.value = false
  }
}

async function handleSummarize() {
  summarizing.value = true
  try {
    const res = await summarizeReq()
    proxy.$modal.msgSuccess(res.msg || '已总结')
    await loadMessages(true)
  } finally {
    summarizing.value = false
  }
}

onMounted(async () => {
  await loadRoom()
  await loadMessages()
  timer = setInterval(() => loadMessages(true), 5000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.req-chat { height: calc(100vh - 120px); }
.shell { height: 100%; background: var(--surface-card, #fff); border-radius: 12px; overflow: hidden; border: 1px solid var(--border-soft, #eef2ff); }
.side { padding: 16px; border-right: 1px solid #eef2ff; background: #f8fafc; }
.side-title { font-weight: 700; }
.side-sub { font-size: 12px; color: #94a3b8; margin: 4px 0 14px; }
.member { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
.m-name { font-size: 13px; font-weight: 600; }
.m-role { font-size: 12px; color: #94a3b8; }
.el-avatar.ai { background: #111827; color: #fff; }
.el-avatar.user { background: #6366f1; color: #fff; }
.main { display: flex; flex-direction: column; padding: 0; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 12px 16px; border-bottom: 1px solid #eef2ff; font-size: 13px; color: #64748b; }
.msgs { flex: 1; overflow: auto; padding: 16px; }
.row { display: flex; margin-bottom: 12px; }
.row.ai { justify-content: flex-start; }
.row.user { justify-content: flex-end; }
.bubble { max-width: 72%; background: #f1f5f9; border-radius: 12px; padding: 10px 12px; }
.row.user .bubble { background: #eef2ff; }
.who { font-size: 12px; color: #64748b; margin-bottom: 4px; span { margin-left: 8px; color: #94a3b8; } }
.body { white-space: pre-wrap; line-height: 1.7; color: #0f172a; }
.composer { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid #eef2ff; align-items: flex-end; }
</style>
