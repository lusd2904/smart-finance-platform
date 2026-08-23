<template>
  <div class="app-container chat-container">
    <el-container style="height: 100%">
      <!-- 侧边栏：会话历史 -->
      <SessionSidebar
        :sessions="sessionList"
        :loading="sessionLoading"
        :current-session-id="currentSessionId"
        @new-chat="clearChat"
        @select="loadSession"
        @delete="handleDeleteSession"
      />

      <!-- 主区域：对话框 -->
      <el-main class="chat-main">
        <div class="chat-header">
          <div class="header-left">
            <span class="header-title">AI 智能助手</span>
          </div>
          <div class="header-right">
            <el-tooltip content="全局参数配置" placement="bottom">
              <el-button icon="Setting" circle style="margin-right: 10px" @click="openConfigDialog"></el-button>
            </el-tooltip>
            <el-select v-model="currentModelId" placeholder="选择模型" size="large" style="width: 210px">
              <el-option
                v-for="item in modelOptions"
                :key="item.modelId"
                :label="`${item.provider}/${item.modelCode}`"
                :value="item.modelId"
              />
            </el-select>
          </div>
        </div>

        <MessageStream
          ref="streamRef"
          :messages="messageList"
          :loading="loading"
          :metrics-visible="userConfig.metricsDefaultVisible"
          :session-agent-data="currentSessionAgentData"
          :model-info="currentModelInfo"
          @copy="copyText"
        />

        <ChatInputArea
          v-model:input-message="inputMessage"
          v-model:input-images="inputImages"
          v-model:is-reasoning="chatConfig.isReasoning"
          :loading="loading"
          :vision-enabled="userConfig.visionEnabled"
          :image-max-size-mb="Number(userConfig.imageMaxSizeMb) || 5"
          :model-info="currentModelInfo"
          @send="handleSend"
          @main-action="handleMainAction"
        />
      </el-main>
    </el-container>

    <!-- 全局配置弹窗 -->
    <UserConfigDialog v-model="showConfigDialog" :config="editingUserConfig" @save="handleSaveConfig" />
  </div>
</template>

<script setup name="AiChat">
import { listModelAll } from '@/api/ai/model'
import {
  listChatSession,
  delChatSession,
  getChatSession,
  getUserChatConfig,
  saveUserChatConfig,
  cancelChatRun
} from '@/api/ai/chat'
import { getToken } from '@/utils/auth'
import { v4 as uuidv4 } from 'uuid'
import SessionSidebar from './components/SessionSidebar.vue'
import MessageStream from './components/MessageStream.vue'
import ChatInputArea from './components/ChatInputArea.vue'
import UserConfigDialog from './components/UserConfigDialog.vue'

const { proxy } = getCurrentInstance()

const modelOptions = ref([])
const currentModelId = ref(undefined)
const messageList = ref([])
const inputMessage = ref('')
const inputImages = ref([])
const loading = ref(false)
const streamRef = ref(null)
const currentSessionId = ref(null)
const showConfigDialog = ref(false)
const sessionList = ref([])
const sessionLoading = ref(false)
const abortController = ref(null)
const currentRunId = ref(null)
const currentSessionAgentData = ref(null)

function generateSessionId() {
  return uuidv4()
}

const chatConfig = reactive({
  temperature: undefined,
  isReasoning: true
})

const userConfig = reactive({
  chatConfigId: undefined,
  userId: undefined,
  temperature: undefined,
  addHistoryToContext: '0',
  numHistoryRuns: 3,
  systemPrompt: '',
  metricsDefaultVisible: '1',
  visionEnabled: '0',
  imageMaxSizeMb: 5,
  createTime: undefined,
  updateTime: undefined
})

const editingUserConfig = reactive({
  chatConfigId: undefined,
  userId: undefined,
  temperature: undefined,
  addHistoryToContext: '0',
  numHistoryRuns: 3,
  systemPrompt: '',
  metricsDefaultVisible: '1',
  visionEnabled: '0',
  imageMaxSizeMb: 5,
  createTime: undefined,
  updateTime: undefined
})

const currentModelInfo = computed(() => {
  if (!currentModelId.value) return null
  return modelOptions.value.find((m) => m.modelId === currentModelId.value)
})

function loadUserConfig() {
  getUserChatConfig().then((res) => {
    if (res.data) {
      Object.assign(userConfig, res.data)
      Object.assign(editingUserConfig, res.data)
    }
  })
}

function openConfigDialog() {
  Object.assign(editingUserConfig, userConfig)
  showConfigDialog.value = true
}

function handleSaveConfig(payload) {
  saveUserChatConfig(payload).then(() => {
    proxy.$modal.msgSuccess('配置保存成功')
    showConfigDialog.value = false
    loadUserConfig()
  })
}

function getModels() {
  listModelAll().then((res) => {
    modelOptions.value = res.data
    if (modelOptions.value.length > 0) {
      currentModelId.value = modelOptions.value[0].modelId
      // 初始化配置
      const model = modelOptions.value[0]
      chatConfig.temperature = model.temperature
    }
  })
}

// 监听模型切换，更新默认配置
watch(currentModelId, (newVal) => {
  const model = modelOptions.value.find((m) => m.modelId === newVal)
  if (model) {
    chatConfig.temperature = model.temperature
  }
})

function getSessions() {
  sessionLoading.value = true
  listChatSession().then((res) => {
    sessionList.value = res.data
    // 按创建时间倒序排序
    if (sessionList.value && sessionList.value.length > 0) {
      sessionList.value.sort((a, b) => {
        const dateA = new Date(a.createdAt).getTime()
        const dateB = new Date(b.createdAt).getTime()
        return dateB - dateA
      })
    }
    sessionLoading.value = false
  })
}

function loadSession(sessionId) {
  if (currentSessionId.value === sessionId) return
  currentSessionId.value = sessionId
  messageList.value = []
  loading.value = true
  getChatSession(sessionId).then((res) => {
    messageList.value = res.data.messages
    currentSessionAgentData.value = res.data.agentData
    loading.value = false
    streamRef.value?.resetAutoScroll()
  })
}

function handleDeleteSession(sessionId) {
  proxy.$modal
    .confirm('是否确认删除该会话？')
    .then(function () {
      return delChatSession(sessionId)
    })
    .then(() => {
      getSessions()
      if (currentSessionId.value === sessionId) {
        clearChat()
      }
      proxy.$modal.msgSuccess('删除成功')
    })
    .catch(() => {})
}

async function sendRequest(text, images) {
  if (!currentModelId.value) {
    proxy.$modal.msgError('请先选择模型')
    return
  }

  loading.value = true
  const imageList = images ? images.slice() : []

  const aiMsgIndex =
    messageList.value.push({
      role: 'assistant',
      content: '',
      reasoningContent: ''
    }) - 1
  streamRef.value?.resetAutoScroll()

  abortController.value = new AbortController()

  try {
    const response = await fetch(import.meta.env.VITE_APP_BASE_API + '/ai/chat/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + getToken()
      },
      signal: abortController.value.signal,
      body: JSON.stringify({
        modelId: currentModelId.value,
        message: text,
        images: imageList,
        sessionId: currentSessionId.value,
        stream: true,
        temperature: chatConfig.temperature,
        isReasoning: chatConfig.isReasoning
      })
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let aiContent = ''
    let aiReasoning = ''
    let buffer = ''
    let needRefreshSessions = false

    while (true) {
      if (!abortController.value) break
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留最后一个可能不完整的行

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          if (data.type === 'content') {
            aiContent += data.content
            messageList.value[aiMsgIndex].content = aiContent
          } else if (data.type === 'reasoning') {
            aiReasoning += data.content
            messageList.value[aiMsgIndex].reasoningContent = aiReasoning
          } else if (data.type === 'meta') {
            currentSessionId.value = data.session_id
            // 如果是新会话，标记需要刷新列表
            if (!sessionList.value.find((s) => s.sessionId === data.session_id)) {
              needRefreshSessions = true
            }
          } else if (data.type === 'run_info') {
            currentRunId.value = data.run_id
          } else if (data.type === 'metrics') {
            messageList.value[aiMsgIndex].metrics = data.metrics
          } else if (data.type === 'error') {
            proxy.$modal.msgError(data.error)
          }
        } catch (e) {
          console.error('Parse error', e)
        }
      }
    }

    // 整个响应结束后，如果需要则刷新会话列表
    if (needRefreshSessions) {
      getSessions()
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // 用户终止
    } else {
      proxy.$modal.msgError('请求失败: ' + err.message)
    }
  } finally {
    loading.value = false
    abortController.value = null
  }
}

function clearChat() {
  messageList.value = []
  currentSessionId.value = generateSessionId()
  currentSessionAgentData.value = null
}

function copyText(text) {
  if (!text) {
    proxy.$modal.msgWarning('内容为空，无法复制')
    return
  }
  navigator.clipboard
    .writeText(text)
    .then(() => {
      proxy.$modal.msgSuccess('复制成功')
    })
    .catch(() => {
      proxy.$modal.msgError('复制失败')
    })
}

async function handleSend() {
  const text = inputMessage.value.trim()
  const images = inputImages.value
  if (!text && !images.length) return
  if (!currentModelId.value) {
    proxy.$modal.msgError('请先选择模型')
    return
  }

  const imageList = images.slice()
  messageList.value.push({ role: 'user', content: text, images: imageList })
  inputMessage.value = ''
  inputImages.value = []
  currentRunId.value = null

  await sendRequest(text, imageList)
}

function stopGeneration() {
  if (abortController.value) {
    const controller = abortController.value
    abortController.value = null
    loading.value = false

    // Send cancellation signal to backend first
    if (currentRunId.value) {
      cancelChatRun(currentRunId.value)
        .then(() => {})
        .catch((err) => {
          console.error('Failed to cancel run:', err)
        })
        .finally(() => {
          // Abort the connection after attempting to cancel on server
          // This ensures the server has time to handle the cancellation and save data
          controller.abort()
        })
    } else {
      controller.abort()
    }
  }
}

function handleMainAction() {
  if (loading.value) {
    stopGeneration()
  } else {
    handleSend()
  }
}

onMounted(() => {
  getModels()
  getSessions()
  loadUserConfig()
})
</script>

<style scoped lang="scss">
.chat-container {
  height: calc(100vh - 84px);
  padding: 0;
  background-color: var(--el-bg-color-page);
  overflow: hidden;
}

.chat-main {
  padding: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color-page);
  position: relative;
  overflow: hidden;

  .chat-header {
    height: 60px;
    background-color: var(--el-bg-color);
    border-bottom: 1px solid var(--el-border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 20px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);

    .header-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }
}
</style>
