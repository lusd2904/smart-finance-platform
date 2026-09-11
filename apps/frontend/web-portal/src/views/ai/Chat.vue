<template>
  <PageFrame
    title="研判工作台"
    subtitle="会话 · transcript · 工具引用 · 标的上下文"
    :loading="loading"
  >
    <template #actions>
      <el-tag v-if="context.symbol" effect="plain" class="symbol-chip">{{ context.symbol }}{{ context.market ? `.${context.market}` : '' }}</el-tag>
      <el-tag effect="plain">默认 {{ defaultModelName }}</el-tag>
      <el-button @click="newSession">+ 新建会话</el-button>
      <el-button type="primary" :loading="sending" @click="oneshot">一键研判</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · 示意会话，不是实盘结论" type="warning" show-icon :closable="false" />

    <div class="chat-shell">
      <aside class="pane glass-panel">
        <h3>会话</h3>
        <button
          v-for="s in sessions"
          :key="s.sessionId || s.id"
          type="button"
          class="session-row"
          :class="{ active: isCurrent(s) }"
          @click="openSession(s)"
        >
          <strong>{{ s.sessionTitle || s.title || s.sessionId }}</strong>
          <span class="muted">{{ s.updatedAt || s.createdAt || '' }} · {{ s.modelName || defaultModelName }}</span>
        </button>
        <el-empty v-if="!sessions.length" description="暂无会话" :image-size="48" />
      </aside>

      <section class="pane glass-panel main-pane">
        <div class="transcript" ref="scrollRef">
          <article v-for="(m, i) in messages" :key="i" class="bubble" :class="m.role">
            <div class="bubble-head">
              <strong>{{ m.role === 'user' ? '你' : '研判' }}</strong>
              <el-tag v-if="m.stance" size="small" :type="stanceType(m.stance)" effect="plain">{{ m.stance }}</el-tag>
              <el-tag v-if="m.stub" size="small" type="warning" effect="plain">STUB</el-tag>
            </div>
            <div v-if="m.tools?.length" class="tool-row">
              <span v-for="t in m.tools" :key="t" class="filter-chip">{{ t }}</span>
            </div>
            <p>{{ m.content }}</p>
          </article>
          <el-empty v-if="!messages.length" description="选择会话或输入问题后发送" :image-size="64" />
        </div>

        <div class="composer">
          <div class="composer-tools">
            <el-select v-model="modelId" placeholder="模型" style="width:180px" filterable>
              <el-option
                v-for="m in models"
                :key="m.modelId || m.modelCode"
                :label="m.modelName || m.modelCode"
                :value="m.modelId || m.modelCode"
              />
            </el-select>
            <el-button @click="ctxOpen = true">挂标的 / 上下文</el-button>
          </div>
          <el-input
            v-model="prompt"
            type="textarea"
            :rows="3"
            placeholder="输入问题 · Enter 发送 · 一键研判走 oneshot"
            @keydown.enter.exact.prevent="send"
          />
          <div class="composer-foot">
            <span class="muted">{{ context.symbol ? `上下文 ${context.symbol}` : '未挂标的' }}</span>
            <el-button type="primary" :loading="sending" @click="send">发送</el-button>
          </div>
        </div>
      </section>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-head">
          <h3>近期研判</h3>
          <span class="muted">optional · 示意条不作为实盘建议</span>
        </div>
      </template>
      <div class="recent-row">
        <article v-for="r in recents" :key="r.symbol" class="recent-card">
          <strong>{{ r.symbol }}</strong>
          <span :class="stanceClass(r.stance)">{{ r.stance }}</span>
          <b class="numeric" :class="scoreClass(r.score)">{{ scoreText(r.score) }}</b>
          <small class="muted">{{ r.note || '' }}</small>
        </article>
        <el-empty v-if="!recents.length" description="暂无近期研判" :image-size="40" />
      </div>
    </el-card>

    <el-dialog v-model="ctxOpen" title="挂标的 / 上下文" width="400px">
      <el-form label-width="72px">
        <el-form-item label="代码"><el-input v-model="ctxDraft.symbol" placeholder="NVDA / 00700" /></el-form-item>
        <el-form-item label="市场">
          <el-select v-model="ctxDraft.market" style="width:100%">
            <el-option label="美股 US" value="US" />
            <el-option label="港股 HK" value="HK" />
            <el-option label="A股 CN" value="CN" />
          </el-select>
        </el-form-item>
        <p class="muted">本地上下文，随 oneshot / 发送一并提交。不假装已接入完整行情快照。</p>
      </el-form>
      <template #footer>
        <el-button @click="ctxOpen = false">取消</el-button>
        <el-button type="primary" @click="applyContext">确定</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>会话 list / transcript · 工具芯片 · tabular-nums · POST /ai/chat/oneshot</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { analyzeOneshot, getChatSession, listChatSession, listModelAll } from '@/api/ai'
import { score100, scoreClass } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { stubChatMessages, stubChatSessions, stubModels, stubRecentVerdicts } from '@/utils/stubs'

const route = useRoute()
const loading = ref(false)
const sending = ref(false)
const usingStub = ref(false)
const sessions = ref([])
const messages = ref([])
const models = ref([])
const modelId = ref('')
const prompt = ref('')
const currentId = ref('')
const ctxOpen = ref(false)
const recents = ref([])
const scrollRef = ref(null)
const context = reactive({ symbol: '', market: 'US' })
const ctxDraft = reactive({ symbol: '', market: 'US' })

const defaultModelName = computed(() => {
  const found = models.value.find((m) => (m.modelId || m.modelCode) === modelId.value)
  return found?.modelName || found?.modelCode || '默认模型'
})

function isCurrent(s) {
  return (s.sessionId || s.id) === currentId.value
}
function stanceType(stance) {
  const s = String(stance || '')
  if (s.includes('多') || s.includes('买')) return 'danger'
  if (s.includes('空') || s.includes('卖')) return 'success'
  return 'info'
}
function stanceClass(stance) {
  const s = String(stance || '')
  if (s.includes('多') || s.includes('买')) return 'up'
  if (s.includes('空') || s.includes('卖')) return 'down'
  return 'flat'
}
function scoreText(v) {
  const n = score100(v)
  return n == null ? '--' : String(n)
}
function scrollBottom() {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

function applyContext() {
  context.symbol = ctxDraft.symbol.trim().toUpperCase()
  context.market = ctxDraft.market
  ctxOpen.value = false
}

function newSession() {
  currentId.value = ''
  messages.value = []
  prompt.value = ''
}

async function loadModels() {
  try {
    const list = unwrapList(await listModelAll())
    if (list.length) {
      models.value = list
      const chat = list.find((m) => m.scope === 'chat' && String(m.status ?? '0') === '0') || list[0]
      modelId.value = chat.modelId || chat.modelCode
      return
    }
  } catch { /* stub */ }
  models.value = stubModels()
  modelId.value = models.value[0].modelId
}

async function loadSessions() {
  loading.value = true
  try {
    const list = unwrapList(await listChatSession())
    if (list.length) {
      sessions.value = list
      usingStub.value = false
      if (!currentId.value) await openSession(list[0])
      return
    }
    applyStubSessions()
  } catch {
    applyStubSessions()
  } finally {
    loading.value = false
  }
}

function applyStubSessions() {
  usingStub.value = true
  sessions.value = stubChatSessions()
  recents.value = stubRecentVerdicts()
  currentId.value = sessions.value[0].sessionId
  messages.value = stubChatMessages(context.symbol || 'NVDA')
}

async function openSession(s) {
  currentId.value = s.sessionId || s.id
  if (usingStub.value) {
    messages.value = stubChatMessages(context.symbol || s.sessionTitle || 'NVDA')
    scrollBottom()
    return
  }
  try {
    const data = unwrap(await getChatSession(currentId.value))
    const rows = data.messages || data.items || []
    messages.value = rows.map((m) => ({
      role: m.role || 'assistant',
      content: m.content || m.answer || '',
      stance: m.stance || m.decision,
      tools: m.tools || m.toolCalls || []
    }))
    if (data.modelId) modelId.value = data.modelId
  } catch {
    messages.value = []
    ElMessage.info('会话详情暂不可用')
  }
  scrollBottom()
}

function pushLocal(role, content, extra = {}) {
  messages.value.push({ role, content, ...extra })
  scrollBottom()
}

function extractAnswer(data) {
  const parsed = data.result || data
  return (
    data.answer ||
    data.content ||
    data.reply ||
    data.summary ||
    parsed.trend_summary ||
    parsed.operation_advice ||
    parsed.summary ||
    ''
  )
}

function extractStance(data) {
  const parsed = data.result || data
  return parsed.decision || parsed.stance || data.direction || ''
}

async function send() {
  const text = prompt.value.trim()
  if (!text) return
  prompt.value = ''
  pushLocal('user', text)
  sending.value = true
  try {
    const payload = {
      prompt: text,
      message: text,
      modelId: modelId.value || undefined,
      sessionId: currentId.value || undefined,
      symbol: context.symbol || undefined,
      market: context.market || undefined
    }
    const data = unwrap(await analyzeOneshot(payload))
    const answer = extractAnswer(data)
    if (answer) {
      pushLocal('assistant', answer, {
        stance: extractStance(data),
        tools: data.tools || ['chat']
      })
      rememberRecent(extractStance(data), score100(data.score || data.result?.score))
    } else {
      pushLocal('assistant', '接口已返回，但没有可读正文。', { stub: true })
    }
  } catch (e) {
    pushLocal('assistant', e?.message || '研判失败', { stub: true })
  } finally {
    sending.value = false
  }
}

async function oneshot() {
  if (!context.symbol && !prompt.value.trim()) {
    ctxDraft.symbol = context.symbol
    ctxDraft.market = context.market
    ctxOpen.value = true
    ElMessage.info('先挂一个标的，或输入问题')
    return
  }
  if (!prompt.value.trim()) {
    prompt.value = `${context.symbol} ${context.market} 全景研判`.trim()
  }
  await send()
}

function rememberRecent(stance, score) {
  if (!context.symbol) return
  recents.value = [
    { symbol: context.symbol, market: context.market, stance: stance || '观望', score, note: '本次 oneshot' },
    ...recents.value.filter((r) => r.symbol !== context.symbol)
  ].slice(0, 6)
}

onMounted(async () => {
  const symbol = String(route.query.symbol || '').trim()
  if (symbol) {
    context.symbol = symbol.toUpperCase()
    context.market = String(route.query.market || 'US').toUpperCase()
    prompt.value = `${context.symbol} ${context.market} 研判`.trim()
  }
  await loadModels()
  await loadSessions()
})
</script>

<style scoped>
.symbol-chip { font-variant-numeric: tabular-nums; }
.chat-shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 10px;
  min-height: 520px;
}
.pane { padding: 10px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.main-pane { min-height: 520px; }
h3 { margin: 0; font-size: 15px; }
.session-row {
  width: 100%;
  display: grid;
  gap: 2px;
  padding: 8px 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.session-row.active {
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
}
.transcript { flex: 1; overflow: auto; display: grid; align-content: start; gap: 10px; }
.bubble {
  padding: 10px;
  border-radius: 10px;
  background: var(--surface-soft);
}
.bubble.user { background: color-mix(in srgb, var(--accent) 10%, transparent); }
.bubble-head, .tool-row, .composer-tools, .composer-foot, .card-head, .recent-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.bubble-head, .composer-foot, .card-head { justify-content: space-between; }
.bubble p { margin: 8px 0 0; line-height: 1.65; white-space: pre-wrap; }
.composer { display: grid; gap: 8px; padding-top: 8px; border-top: 1px solid var(--border-soft); }
.recent-card {
  min-width: 120px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--surface-soft);
  display: grid;
  gap: 4px;
}
.muted { color: var(--text-secondary); font-size: 12px; }
@media (max-width: 900px) {
  .chat-shell { grid-template-columns: 1fr; }
}
</style>
