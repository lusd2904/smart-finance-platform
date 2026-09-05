<template>
  <nav class="m-tabbar" aria-label="底部导航">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="m-tabbar__item"
      :class="{ 'is-on': active === tab.key }"
    >
      <span class="m-tabbar__icon">
        <svg v-if="tab.key === 'sentiment'" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 14c3-6 6-6 8 0s5 6 8 0"/><circle cx="12" cy="12" r="9"/></svg>
        <svg v-else-if="tab.key === 'picks'" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l2.2 6.6H21l-5.4 4 2.1 6.4L12 16.8 6.3 20l2.1-6.4L3 9.6h6.8z"/></svg>
        <svg v-else-if="tab.key === 'heat'" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3s5 5.2 5 9a5 5 0 11-10 0c0-2.2 1.6-4.6 3-6.2.6 2.2 2 3.4 2 3.4S13.6 7.8 12 3z"/></svg>
        <svg v-else-if="tab.key === 'positions'" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M3 10h18M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.2"/><path d="M5 19c1.4-3.2 4-5 7-5s5.6 1.8 7 5"/></svg>
      </span>
      <span class="m-tabbar__label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup>
const tabs = [
  { key: 'sentiment', path: '/m/sentiment', label: '舆情' },
  { key: 'picks', path: '/m/picks', label: '选股' },
  { key: 'heat', path: '/m', label: '热度' },
  { key: 'positions', path: '/m/positions', label: '持仓' },
  { key: 'me', path: '/m/me', label: '我的' }
]

const route = useRoute()
const active = computed(() => {
  const p = route.path
  if (p.startsWith('/m/sentiment')) return 'sentiment'
  if (p.startsWith('/m/picks')) return 'picks'
  if (p.startsWith('/m/positions')) return 'positions'
  if (p.startsWith('/m/me')) return 'me'
  return 'heat'
})
</script>

<style scoped lang="scss">
.m-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  display: flex;
  height: calc(52px + env(safe-area-inset-bottom, 0px));
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: #fff;
  border-top: 1px solid #ececef;
}

.m-tabbar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: #8b8d98;
  text-decoration: none;
}

.m-tabbar__item.is-on {
  color: #111827;
}

.m-tabbar__icon {
  display: flex;
  line-height: 0;
}

.m-tabbar__label {
  font-size: 10px;
  font-weight: 600;
}
</style>
