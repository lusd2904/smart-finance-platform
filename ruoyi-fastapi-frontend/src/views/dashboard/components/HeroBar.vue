<template>
  <div class="hero-card">
    <div class="hero-left">
      <div class="hero-greet">{{ greetText }}，{{ displayName }}</div>
      <div class="hero-sub">智慧金融分析平台 · 均衡总览</div>
      <div class="hero-time">
        {{ nowText }} · 数据截至 {{ summary.generatedAt || '--' }}
        <el-tag v-if="summary.cached" size="small" effect="plain" class="cache-tag">缓存</el-tag>
      </div>
    </div>
    <div class="hero-actions">
      <button
        v-for="s in sessions"
        :key="s.market"
        type="button"
        class="session-chip"
        :class="`status-${s.status}`"
        :title="`${s.label} ${s.localDate} ${s.localTime} (${s.timezone})`"
      >
        <span class="session-dot"></span>
        {{ s.label }} {{ sessionText(s) }}
      </button>
      <el-button type="primary" icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新</el-button>
    </div>
  </div>
</template>

<script setup name="DashHeroBar">
import useUserStore from '@/store/modules/user'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false }
})
defineEmits(['refresh'])

const userStore = useUserStore()
const nowText = ref('')
const displayName = computed(() => userStore.nickName || userStore.name || '管理员')
const greetText = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const sessions = computed(() =>
  [
    { market: 'US', label: '美股' },
    { market: 'HK', label: '港股' },
    { market: 'CN', label: 'A股' }
  ].map(m => {
    const found = (props.summary.sessions || []).find(s => s.market === m.market)
    return found ? { ...m, ...found } : { ...m, status: 'unknown' }
  })
)

function sessionText(s) {
  if (s.status === 'open') return '开市'
  if (s.status === 'weekend') return '休市'
  if (s.status === 'closed') return '已收盘'
  return '--'
}

let timer = null
function tick() {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  nowText.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
onMounted(() => {
  tick()
  timer = setInterval(tick, 30000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped lang="scss">
.hero-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 20px 24px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 45%, #7c3aed 100%);
  box-shadow: 0 12px 30px rgba(79, 70, 229, 0.25);
}

.hero-greet {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 4px;
}

.hero-sub {
  opacity: 0.92;
  font-size: 13px;
}

.hero-time {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.85;
  display: flex;
  align-items: center;
  gap: 6px;
}

.cache-tag {
  --el-tag-text-color: #fff;
  --el-tag-border-color: rgba(255, 255, 255, 0.5);
  --el-tag-bg-color: transparent;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.session-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 12px;
  cursor: default;

  .session-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #94a3b8;
  }

  &.status-open .session-dot {
    background: #34d399;
    box-shadow: 0 0 6px rgba(52, 211, 153, 0.9);
  }

  &.status-closed .session-dot {
    background: #fbbf24;
  }

  &.status-weekend .session-dot {
    background: #94a3b8;
  }
}

@media (max-width: 768px) {
  .hero-greet {
    font-size: 18px;
  }
}
</style>
