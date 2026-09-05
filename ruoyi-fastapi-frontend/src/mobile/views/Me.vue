<template>
  <div class="m-page m-me">
    <PullRefresh :refreshing="refreshing" @refresh="refresh">
      <header class="m-me__hero">
        <div class="m-me__avatar">{{ initial }}</div>
        <div>
          <div class="m-me__nick">{{ nickName || '未登录' }}</div>
          <div class="m-me__user">{{ userName }}</div>
        </div>
      </header>
      <section class="m-card">
        <div class="m-card__h">网关状态</div>
        <p class="m-me__gw">{{ gateway.base }}</p>
        <p class="m-me__st" :class="gatewayClass">
          {{ gatewayLabel }}
        </p>
      </section>
      <EmptyState v-if="error" :message="error" retry @retry="refresh" />
      <button type="button" class="m-me__out" @click="askLogout = true">退出登录</button>
      <div v-if="askLogout" class="m-card">
        <p>确定退出登录吗？</p>
        <div class="m-me__confirm">
          <button type="button" @click="askLogout = false">取消</button>
          <button type="button" class="danger" @click="handleLogout">退出</button>
        </div>
      </div>
    </PullRefresh>
  </div>
</template>

<script setup name="MobileMe">
import useUserStore from '@/store/modules/user'
import { removeToken } from '@/utils/auth'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import { probeGateway } from '../utils/gateway'

const userStore = useUserStore()
const router = useRouter()
const refreshing = ref(false)
const error = ref('')
const probed = ref(false)
const askLogout = ref(false)
const gateway = reactive({ ok: false, base: '', status: 0, ms: 0, error: '' })

const nickName = computed(() => userStore.nickName || '')
const userName = computed(() => userStore.name || '')
const initial = computed(() => (nickName.value || userName.value || 'U').slice(0, 1))
const gatewayLabel = computed(() => {
  if (!probed.value) return '探测中…'
  if (gateway.ok) return `在线 · HTTP ${gateway.status} · ${gateway.ms}ms`
  if (gateway.error === 'timeout') return '探测失败（超时）'
  if (gateway.error === 'unreachable') return '探测失败'
  return `探测失败${gateway.status ? ' · HTTP ' + gateway.status : ''}`
})
const gatewayClass = computed(() => {
  if (!probed.value) return ''
  return gateway.ok ? 'is-ok' : 'm-down'
})

async function loadInfo() {
  if (!userStore.name && !userStore.nickName) {
    await userStore.getInfo()
  }
}

async function loadGateway() {
  const r = await probeGateway()
  Object.assign(gateway, r)
  probed.value = true
}

async function refresh() {
  refreshing.value = true
  error.value = ''
  try {
    await Promise.all([loadInfo(), loadGateway()])
  } catch (e) {
    error.value = (e && e.message) || '刷新失败'
  } finally {
    refreshing.value = false
  }
}

async function handleLogout() {
  askLogout.value = false
  try {
    await userStore.logOut()
  } catch {
    /* API may fail; local token must still go */
  }
  userStore.token = ''
  userStore.roles = []
  userStore.permissions = []
  removeToken()
  router.replace('/m/login')
}

onMounted(refresh)
</script>

<style scoped lang="scss">
.m-me__hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px 16px 8px;
}
.m-me__avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
}
.m-me__nick { font-size: 20px; font-weight: 800; }
.m-me__user { color: #8b8d98; font-size: 13px; margin-top: 2px; }
.m-card__h { font-size: 13px; font-weight: 700; margin-bottom: 6px; }
.m-me__gw { margin: 0; color: #6b7280; font-size: 13px; word-break: break-all; }
.m-me__st { margin: 6px 0 0; font-size: 14px; font-weight: 700; }
.m-me__st.is-ok { color: #30a46c; }
.m-me__confirm {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.m-me__confirm button {
  flex: 1;
  height: 40px;
  border: 1px solid #ececef;
  border-radius: 8px;
  background: #fff;
  font-weight: 700;
}
.m-me__confirm .danger {
  background: #e5484d;
  border-color: #e5484d;
  color: #fff;
}
.m-me__out {
  display: block;
  width: calc(100% - 32px);
  margin: 24px 16px;
  height: 44px;
  border: 0;
  border-radius: 10px;
  background: #fff;
  color: #e5484d;
  font-weight: 700;
  border: 1px solid #ececef;
}
</style>
