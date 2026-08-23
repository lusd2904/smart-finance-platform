<template>
  <el-aside width="260px" class="session-sidebar">
    <div class="sidebar-header">
      <el-button type="primary" class="new-chat-btn" icon="Plus" @click="emit('new-chat')">新建对话</el-button>
    </div>
    <div class="session-list" v-loading="loading">
      <div
        v-for="session in sessions"
        :key="session.sessionId"
        :class="['session-item', currentSessionId === session.sessionId ? 'active' : '']"
        @click="emit('select', session.sessionId)"
      >
        <div class="session-icon">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <div class="session-info">
          <div class="session-title">{{ session.sessionTitle || '新对话' }}</div>
          <div class="session-time">{{ formatTime(session.createdAt) }}</div>
        </div>
        <el-button
          class="delete-btn"
          type="danger"
          link
          icon="Delete"
          @click.stop="emit('delete', session.sessionId)"
        ></el-button>
      </div>
      <div v-if="sessions.length === 0 && !loading" class="empty-session">暂无历史对话</div>
    </div>
  </el-aside>
</template>

<script setup name="AiChatSessionSidebar">
import { formatTime } from '../utils'

defineProps({
  sessions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  currentSessionId: { type: String, default: null }
})

const emit = defineEmits(['new-chat', 'select', 'delete'])
</script>

<style scoped lang="scss">
@use './sidebar.scss';
</style>
