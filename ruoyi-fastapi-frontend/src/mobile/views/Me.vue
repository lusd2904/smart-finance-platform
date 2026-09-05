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
        <p class="m-me__st" :class="gateway.ok ? 'm-up' : 'm-down'">
          {{ gatewayLabel }}
        </p>
      </section>
      <EmptyState v-if="error" :message="error" retry @retry="refresh" />
      <button type="button" class="m-me__out" @click="handleLogout">退出登录</button>
    </PullRefresh>
  </div>
</template>

<script setup name="MobileMe">
import useUserStore from '@/store/modules/user'
import PullRefresh from '../components/PullRefresh.vue'
import EmptyState from '../components/EmptyState.vue'
import { probeGateway } from '../utils/gateway'

const userStore = useUserStore()
const router = useRouter()
const refreshing = ref(false)
const error = ref('')
const gateway = reactive({ ok: false, base: '', status: 0, ms: 0, error: '' })

const nickName = computed(() => userStore.nickName || '')
const userName = computed(() => userStore.name || '')
const initial = computed(() => (nickName.value || userName.value || 'U').slice(0, 1))
const gatewayLabel = computed(() => {
  if (gateway.error === 'timeout') return `探测超时（${gateway.ms}ms）`
  if (gateway.ok) return `在线 · HTTP ${gateway.status} · ${gateway.ms}ms`
  return gateway.error === 'unreachable' ? '不可达（客户端探测）' : `异常 · HTTP ${gateway.status || '--'}`
})

async function loadInfo() {
  if (!userStore.name && !userStore.nickName) {
    await userStore.getInfo()
  }
}

async function loadGateway() {
  const r = await probeGateway()
  Object.assign(gateway, r)
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
  if (!window.confirm('确定退出登录吗？')) return
  try {
    await userStore.logOut()
  } catch {
    /* token still cleared by store on most paths; force leave */
  }
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
