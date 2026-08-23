<template>
  <div class="chat-history" ref="chatHistoryRef" @scroll="handleScroll">
    <div class="chat-content" ref="chatContentRef" :class="{ 'is-empty': messages.length === 0 }">
      <div v-if="messages.length === 0" class="welcome-screen">
        <div class="welcome-icon">
          <el-icon size="60"><Service /></el-icon>
        </div>
        <h2>你好！我是你的 AI 助手</h2>
        <p>请在下方输入问题开始对话...</p>
      </div>

      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message-row', msg.role === 'user' ? 'message-user' : 'message-ai']"
      >
        <div class="message-avatar">
          <el-avatar
            :icon="msg.role === 'user' ? 'UserFilled' : 'Service'"
            :size="40"
            :class="msg.role === 'user' ? 'avatar-user' : 'avatar-ai'"
          ></el-avatar>
        </div>
        <div class="message-content-wrapper">
          <div class="message-sender">
            {{ msg.role === 'user' ? '我' : 'AI 助手' }}
            <span class="message-time" v-if="msg.createdAt">{{ formatTime(msg.createdAt) }}</span>
          </div>
          <div class="message-bubble">
            <div v-if="msg.role === 'user'">
              <div v-if="msg.images && msg.images.length > 0" class="user-images">
                <el-image
                  v-for="(img, idx) in msg.images"
                  :key="idx"
                  :src="getImageUrl(img)"
                  :preview-src-list="msg.images.map(getImageUrl)"
                  fit="cover"
                  class="user-image-item"
                />
              </div>
              <div class="user-text">{{ msg.content }}</div>
            </div>
            <AiMessage
              v-else
              :content="msg.content"
              :reasoning-content="msg.reasoningContent"
              :loading="loading && index === messages.length - 1"
            />
          </div>
          <div class="message-footer">
            <div class="footer-actions">
              <el-tooltip content="复制" placement="top">
                <el-button
                  link
                  type="info"
                  :icon="DocumentCopy"
                  size="small"
                  @click="copyMessage(msg.content)"
                ></el-button>
              </el-tooltip>
              <div v-if="metricsVisible == '0' && hasMetrics(msg)" class="message-metrics">
                <span v-if="msg.metrics?.duration !== null && msg.metrics?.duration !== undefined">
                  耗时 {{ msg.metrics.duration.toFixed(3) }} s
                </span>
                <span v-if="msg.metrics?.inputTokens !== null && msg.metrics?.inputTokens !== undefined">
                  输入 {{ msg.metrics.inputTokens }} tokens
                </span>
                <span v-if="msg.metrics?.outputTokens !== null && msg.metrics?.outputTokens !== undefined">
                  输出 {{ msg.metrics.outputTokens }} tokens
                </span>
                <span v-if="msg.metrics?.totalTokens !== null && msg.metrics?.totalTokens !== undefined">
                  总 {{ msg.metrics.totalTokens }} tokens
                </span>
                <span v-if="msg.metrics?.reasoningTokens !== null && msg.metrics?.reasoningTokens !== undefined">
                  推理 {{ msg.metrics.reasoningTokens }} tokens
                </span>
              </div>
            </div>
            <div v-if="msg.role === 'assistant'" class="model-info">
              <el-tag size="small" type="info" effect="plain" v-if="sessionAgentData?.model">
                {{ sessionAgentData.model.provider }} / {{ sessionAgentData.model.id }}
              </el-tag>
              <el-tag size="small" type="info" effect="plain" v-else-if="modelInfo">
                {{ modelInfo.provider }} / {{ modelInfo.modelCode }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup name="AiChatMessageStream">
import { DocumentCopy } from '@element-plus/icons-vue'
import { useResizeObserver } from '@vueuse/core'
import AiMessage from './AiMessage.vue'
import { formatTime, getImageUrl } from '../utils'

defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  metricsVisible: { type: String, default: '1' },
  sessionAgentData: { type: Object, default: null },
  modelInfo: { type: Object, default: null }
})

const emit = defineEmits(['copy'])

const chatHistoryRef = ref(null)
const chatContentRef = ref(null)
const isAutoScroll = ref(true)
const isProgrammaticScroll = ref(false)
let scrollTimeout = null

function hasMetrics(msg) {
  const m = msg?.metrics
  if (!m) return false
  return (
    (m.inputTokens !== null && m.inputTokens !== undefined) ||
    (m.outputTokens !== null && m.outputTokens !== undefined) ||
    (m.totalTokens !== null && m.totalTokens !== undefined) ||
    (m.reasoningTokens !== null && m.reasoningTokens !== undefined) ||
    (m.duration !== null && m.duration !== undefined)
  )
}

function copyMessage(text) {
  emit('copy', text)
}

function handleScroll(e) {
  if (isProgrammaticScroll.value) return

  const { scrollTop, scrollHeight, clientHeight } = e.target
  const distanceToBottom = scrollHeight - scrollTop - clientHeight

  // If user scrolls up (distance from bottom > 100px), disable auto-scroll
  if (distanceToBottom > 100) {
    isAutoScroll.value = false
  } else if (distanceToBottom < 20) {
    // If user scrolls back to bottom, re-enable auto-scroll
    isAutoScroll.value = true
  }
}

function scrollToBottom() {
  if (isAutoScroll.value && chatHistoryRef.value) {
    isProgrammaticScroll.value = true

    // Force scroll to bottom immediately
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight

    // Double check in next frames to catch layout shifts (like Mermaid rendering)
    requestAnimationFrame(() => {
      if (chatHistoryRef.value && isAutoScroll.value) {
        chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
      }
    })

    // Reset flag after a short delay, clearing any previous timer
    if (scrollTimeout) clearTimeout(scrollTimeout)

    scrollTimeout = setTimeout(() => {
      isProgrammaticScroll.value = false
      scrollTimeout = null
    }, 100)
  }
}

function resetAutoScroll() {
  isAutoScroll.value = true
  scrollToBottom()
}

// 监听内容变化，自动滚动
useResizeObserver(chatContentRef, () => {
  if (isAutoScroll.value) {
    scrollToBottom()
  }
})

onBeforeUnmount(() => {
  if (scrollTimeout) clearTimeout(scrollTimeout)
})

defineExpose({ scrollToBottom, resetAutoScroll })
</script>

<style scoped lang="scss">
@use './stream.scss';
</style>
