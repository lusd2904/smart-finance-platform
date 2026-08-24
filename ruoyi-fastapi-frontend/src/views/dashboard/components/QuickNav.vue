<template>
  <div class="quick-nav">
    <div v-for="nav in navItems" :key="nav.path" class="nav-item" @click="go(nav.path)">
      <el-icon :size="16" class="nav-icon"><component :is="nav.icon" /></el-icon>
      <span class="nav-title">{{ nav.title }}</span>
    </div>
  </div>
</template>

<script setup name="DashQuickNav">
const router = useRouter()

const navItems = [
  { title: '舆情大盘', path: '/sentiment/dashboard', icon: 'DataAnalysis' },
  { title: '资讯列表', path: '/sentiment/news', icon: 'Reading' },
  { title: '行情中心', path: '/market/heat', icon: 'TrendCharts' },
  { title: '行情台', path: '/market/board', icon: 'DataLine' },
  { title: '财经简报', path: '/market/finance-news', icon: 'Notebook' },
  { title: '量化策略', path: '/quant/strategy', icon: 'Cpu' },
  { title: '自选池', path: '/quant/watchlist', icon: 'Star' },
  { title: '行情自选', path: '/market/watchlist', icon: 'Aim' },
  { title: '市场分析', path: '/market/review', icon: 'Notebook' },
  { title: '交易终端', path: '/trade/trading', icon: 'SwitchButton' },
  { title: '自动分析', path: '/analysis/jobs', icon: 'Clock' }
]

function go(path) {
  router.push(path).catch(() => {})
}
</script>

<style scoped lang="scss">
.quick-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: var(--surface-hover, #eef2ff);
    transform: translateY(-1px);
  }

  .nav-icon {
    color: var(--el-color-primary);
  }
}

.nav-title {
  font-size: 13px;
  color: var(--text-emphasis, #0f172a);
}
</style>
