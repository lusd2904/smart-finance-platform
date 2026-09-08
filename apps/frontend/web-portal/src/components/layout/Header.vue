<template>
  <header class="header">
    <div class="header-right">
      <div class="market-status-container">
        <div v-for="item in sessions" :key="item.market" class="market-status">
          <span class="status-label">{{ item.label }}</span>
          <span class="status-dot" :class="item.status"></span>
          <span class="status-text">{{ item.text }}</span>
        </div>
      </div>
      <ThemeSwitcher />
      <div class="user-info">
        <el-dropdown>
          <div class="user-dropdown">
            <el-avatar :size="34">{{ userInitial }}</el-avatar>
            <div class="user-copy">
              <strong>{{ userStore.displayName }}</strong>
              <span>{{ roleLabel }}</span>
            </div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/index')">工作台</el-dropdown-item>
              <el-dropdown-item @click="router.push('/trade/terminal')">行情交易</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import ThemeSwitcher from './ThemeSwitcher.vue'
import { useUserStore } from '@/store/user'
import { getDashboardSummary } from '@/api/dashboard'
import { stubDashboard } from '@/utils/stubs'

const router = useRouter()
const userStore = useUserStore()
const sessions = ref([
  { market: 'US', label: '美股', status: 'closed', text: '加载中' },
  { market: 'HK', label: '港股', status: 'closed', text: '加载中' },
  { market: 'CN', label: 'A股', status: 'closed', text: '加载中' }
])

const userInitial = computed(() => (userStore.displayName || 'U').slice(0, 1).toUpperCase())
const roleLabel = computed(() => (userStore.usingStub ? '演示会话' : '平台用户'))

function sessionText(s) {
  if (s.status === 'open') return '开市'
  if (s.status === 'weekend') return '休市'
  if (s.status === 'closed') return '已收盘'
  return s.status_text || '--'
}

async function loadSessions() {
  try {
    const res = await getDashboardSummary()
    const list = res?.data?.sessions || res?.sessions || []
    if (list.length) {
      sessions.value = ['US', 'HK', 'CN'].map((m) => {
        const found = list.find((s) => s.market === m) || {}
        const label = m === 'US' ? '美股' : m === 'HK' ? '港股' : 'A股'
        return { market: m, label, status: found.status || 'closed', text: sessionText(found) }
      })
      return
    }
  } catch { /* fall through */ }
  const stub = stubDashboard().sessions
  sessions.value = stub.map((s) => ({
    market: s.market,
    label: s.label,
    status: s.status,
    text: sessionText(s)
  }))
}

const handleLogout = async () => {
  await userStore.logOut()
  ElMessage.success('已退出登录')
  router.push('/login')
}

let timer
onMounted(() => {
  loadSessions()
  timer = window.setInterval(loadSessions, 60000)
})
onUnmounted(() => timer && clearInterval(timer))
</script>

<style scoped lang="scss">
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-soft);
  background: var(--chrome-surface);
  backdrop-filter: var(--chrome-backdrop);
  -webkit-backdrop-filter: var(--chrome-backdrop);
  box-shadow: var(--chrome-shadow), var(--chrome-inset);
}

.header-right,
.market-status-container,
.market-status,
.user-dropdown {
  display: flex;
  align-items: center;
}

.header-right {
  gap: 10px;
  flex-wrap: wrap;
}

.market-status-container {
  gap: 8px;
  flex-wrap: wrap;
}

.market-status {
  gap: 7px;
  padding: 7px 10px;
  border-radius: 12px;
  background: var(--surface-soft);
}

.status-label { color: var(--text-secondary); font-size: 12px; }
.status-text { color: var(--text-emphasis); font-size: 12px; }

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-secondary) 42%, transparent);
  &.open { background: var(--success); box-shadow: 0 0 14px color-mix(in srgb, var(--success) 45%, transparent); }
  &.closed { background: color-mix(in srgb, var(--text-secondary) 42%, transparent); }
}

.user-dropdown {
  gap: 8px;
  padding: 7px 10px;
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--text-primary);
  cursor: pointer;
}

.user-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  strong { color: var(--text-emphasis); font-size: 13px; }
  span { color: var(--text-secondary); font-size: 11px; }
}

@media (max-width: 720px) {
  .user-copy { display: none; }
}
</style>
