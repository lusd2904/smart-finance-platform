<template>
  <div class="portal-container" :data-theme="themeKey">
    <!-- 原项目级赛博动态背景：节点连线 + 穿梭光 -->
    <CyberBackground />

    <div class="portal-top-bar">
      <div class="logo">
        <h2 class="glow-title">智慧金融 · NEXUS</h2>
        <span class="logo-sub">QUANT · SENTIMENT · MARKET</span>
      </div>
      <div class="top-bar-actions">
        <button class="theme-pill glass-panel" type="button" @click="toggleTheme">
          <el-icon><component :is="isDark ? 'Sunny' : 'Moon'" /></el-icon>
          <span>{{ isDark ? '浅色模式' : '深色模式' }}</span>
        </button>
        <el-dropdown>
          <div class="user-dropdown glass-panel">
            <el-avatar :size="32">{{ userInitial }}</el-avatar>
            <div class="user-copy">
              <strong>{{ displayName }}</strong>
              <span>{{ roleLabel }}</span>
            </div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/user/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item @click="router.push('/index')">工作台首页</el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div class="portal-content">
      <header class="portal-header">
        <h1 class="portal-title">量化交易与 AI 研判综合指挥中心</h1>
        <p class="portal-subtitle">QUANTITATIVE TRADING & AI ANALYSIS COMMAND CENTER</p>
        <div class="status-row">
          <span class="pulse-dot"></span>
          <span>NEXUS AI Core Active · Influx 时序在线 · 证券级通道</span>
        </div>
      </header>

      <div class="portal-grid">
        <div
          v-for="group in subsystemGroups"
          :key="group.id"
          class="module-card glass-panel"
          @click="navigateTo(group.path)"
        >
          <div class="module-icon-wrap">
            <el-icon class="module-icon"><component :is="group.icon" /></el-icon>
          </div>
          <div class="module-info">
            <h3 class="module-name">{{ group.name }}</h3>
            <p class="module-desc">{{ group.desc }}</p>
          </div>
          <div class="module-links" @click.stop>
            <button
              v-for="link in group.links"
              :key="link.path"
              type="button"
              class="module-link"
              @click="navigateTo(link.path)"
            >
              {{ link.name }}
            </button>
          </div>
          <div class="module-enter">进入 {{ group.name }} →</div>
        </div>
      </div>

      <footer class="portal-footer">
        <p>系统版本 V2.0 · {{ footerContent }}</p>
      </footer>
    </div>
  </div>
</template>

<script setup name="Portal">
import { computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  Histogram, TrendCharts, Money, DataAnalysis, Monitor, Warning, ArrowDown
} from '@element-plus/icons-vue'
import CyberBackground from '@/components/CyberBackground/index.vue'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import defaultSettings from '@/settings'

const router = useRouter()
const userStore = useUserStore()
const settingsStore = useSettingsStore()
const footerContent = defaultSettings.footerContent

const isDark = computed(() => settingsStore.isDark)
const themeKey = computed(() => (isDark.value ? 'glass-dark' : 'glass-light'))
const displayName = computed(() => userStore.nickName || userStore.name || '用户')
const userInitial = computed(() => String(displayName.value).slice(0, 1).toUpperCase())
const roleLabel = computed(() => {
  const roles = userStore.roles || []
  if (roles.includes('admin')) return '超级管理员'
  return '平台用户'
})

const subsystemGroups = [
  {
    id: 'sentiment-ai',
    name: '舆情与 AI 研判',
    desc: '中文舆情采集、大盘影响研判与统一模型对话',
    path: '/sentiment/dashboard',
    icon: DataAnalysis,
    links: [
      { name: '舆情 AI 大盘', path: '/sentiment/dashboard' },
      { name: 'AI 研判工作台', path: '/market/ai-workbench' },
      { name: 'AI 助手', path: '/ai/chat' }
    ]
  },
  {
    id: 'market',
    name: '行情中心',
    desc: '市场热度、报价台、自选与财经资讯',
    path: '/market/heat',
    icon: Histogram,
    links: [
      { name: '市场热度', path: '/market/heat' },
      { name: '行情台', path: '/market/board' },
      { name: '自选清单', path: '/market/watchlist' }
    ]
  },
  {
    id: 'trade',
    name: '核心交易',
    desc: '报价下单、持仓订单、券商通道与通知',
    path: '/trade/trading',
    icon: Money,
    links: [
      { name: '核心交易台', path: '/trade/trading' },
      { name: '持仓与订单', path: '/trade/positions' },
      { name: '券商账户', path: '/trade/broker' },
      { name: '通知中心', path: '/trade/notifications' }
    ]
  },
  {
    id: 'quant',
    name: '量化策略',
    desc: '多因子信号、档位阈值与 Influx 回测',
    path: '/quant/strategy',
    icon: TrendCharts,
    links: [
      { name: '量化策略中心', path: '/quant/strategy' },
      { name: '策略配置', path: '/quant/strategy-config' },
      { name: '策略回测', path: '/trade/backtest' }
    ]
  },
  {
    id: 'risk',
    name: '风控管理',
    desc: '规则、扫描与风险事件',
    path: '/trade/risk',
    icon: Warning,
    links: [
      { name: '风控管理', path: '/trade/risk' }
    ]
  },
  {
    id: 'platform',
    name: '平台工作台',
    desc: '业务总览、行情快照与系统监控',
    path: '/index',
    icon: Monitor,
    links: [
      { name: '工作台首页', path: '/index' },
      { name: '自动分析任务', path: '/analysis/jobs' },
      { name: '系统监控', path: '/monitor/job' }
    ]
  }
]

function navigateTo(path) {
  router.push(path).catch(() => router.push('/index'))
}

function toggleTheme() {
  settingsStore.toggleTheme()
}

function applyThemeAttr() {
  settingsStore.applyTheme()
}

function handleLogout() {
  ElMessageBox.confirm('确定退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    userStore.logOut().then(() => router.push('/login'))
  }).catch(() => {})
}

onMounted(() => {
  // 门户默认强调深色指挥中心氛围（若用户未开 dark，仍可用 glass-light 变量）
  applyThemeAttr()
})

onBeforeUnmount(() => {
  // 离开门户时保留用户主题选择，不强制清理
})

watch(isDark, () => applyThemeAttr())
</script>

<style scoped lang="scss">
.portal-container {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: transparent;
}

/* 深色指挥中心背景（多层径向光） */
.portal-container[data-theme='glass-dark'] {
  background:
    radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.42) 0%, transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(147, 51, 234, 0.4) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(16, 185, 129, 0.22) 0%, transparent 60%),
    #020617;
  color: #e2e8f0;
}

/* 浅色玻璃光晕 */
.portal-container[data-theme='glass-light'] {
  background:
    radial-gradient(circle at 10% 20%, rgba(96, 165, 250, 0.55) 0%, transparent 45%),
    radial-gradient(circle at 90% 80%, rgba(192, 132, 252, 0.5) 0%, transparent 45%),
    radial-gradient(circle at 50% 50%, rgba(52, 211, 153, 0.35) 0%, transparent 60%),
    #e2e8f0;
  color: #0f172a;
}

.portal-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 22px 40px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
}

.logo {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.glow-title {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: 2px;
  background: linear-gradient(90deg, #38bdf8, #a78bfa, #34d399);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 18px rgba(56, 189, 248, 0.35));
}

.logo-sub {
  font-size: 11px;
  letter-spacing: 2px;
  opacity: 0.65;
}

.top-bar-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.theme-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  cursor: pointer;
  padding: 8px 14px;
  border-radius: 999px !important;
  font-size: 13px;
  color: inherit;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px 6px 6px;
  cursor: pointer;
  border-radius: 99px !important;
  transition: transform 0.2s;
}
.user-dropdown:hover {
  transform: translateY(-1px);
}

.user-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  strong {
    font-size: 13px;
    font-weight: 600;
  }
  span {
    font-size: 11px;
    opacity: 0.7;
    margin-top: 2px;
  }
}

.portal-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 1280px;
  padding: 112px 28px 40px;
}

.portal-header {
  text-align: center;
  margin-bottom: 42px;
}

.portal-title {
  font-size: clamp(1.7rem, 3.2vw, 2.7rem);
  letter-spacing: 4px;
  margin: 0 0 12px;
  font-weight: 750;
}

.portal-subtitle {
  font-size: 0.92rem;
  letter-spacing: 5px;
  margin: 0 0 14px;
  opacity: 0.72;
}

.status-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  opacity: 0.8;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.2);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #39ff14;
  box-shadow: 0 0 12px #39ff14;
  animation: pulse 1.6s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.85); }
}

.portal-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
  width: 100%;
}

.module-card {
  display: flex;
  flex-direction: column;
  padding: 26px 22px 18px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  text-align: center;
  min-height: 248px;
}

.module-card:hover {
  transform: translateY(-8px);
  border-color: rgba(0, 240, 255, 0.35) !important;
  box-shadow: 0 16px 40px rgba(0, 192, 255, 0.16) !important;
}

.module-icon-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 18px;
  border-radius: 16px;
  background: rgba(0, 240, 255, 0.1);
  color: #00f0ff;
  transition: all 0.3s ease;
}

.portal-container[data-theme='glass-light'] .module-icon-wrap {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}

.module-card:hover .module-icon-wrap {
  background: linear-gradient(135deg, #00c3ff, #6366f1);
  color: #fff;
  box-shadow: 0 8px 24px rgba(0, 195, 255, 0.4);
}

.module-icon {
  font-size: 30px;
}

.module-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.module-name {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 650;
  letter-spacing: 1px;
}

.module-desc {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.55;
  opacity: 0.75;
}

.module-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}

.module-link {
  border: 1px solid rgba(56, 189, 248, 0.28);
  background: rgba(56, 189, 248, 0.08);
  color: inherit;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  letter-spacing: 0.4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.module-link:hover {
  border-color: rgba(0, 240, 255, 0.55);
  background: rgba(0, 195, 255, 0.18);
  color: #7dd3fc;
}

.portal-container[data-theme='glass-light'] .module-link {
  border-color: rgba(37, 99, 235, 0.2);
  background: rgba(37, 99, 235, 0.08);
}

.portal-container[data-theme='glass-light'] .module-link:hover {
  border-color: rgba(37, 99, 235, 0.45);
  background: rgba(37, 99, 235, 0.14);
  color: #1d4ed8;
}

.module-enter {
  margin-top: 14px;
  font-size: 12px;
  letter-spacing: 1px;
  color: #00c3ff;
  opacity: 0;
  transform: translateY(4px);
  transition: all 0.25s ease;
}

.portal-container[data-theme='glass-light'] .module-enter {
  color: #2563eb;
}

.module-card:hover .module-enter {
  opacity: 1;
  transform: translateY(0);
}

.portal-footer {
  margin-top: 48px;
  font-size: 0.84rem;
  letter-spacing: 1px;
  opacity: 0.65;
  text-align: center;
}

/* 玻璃拟态 */
.glass-panel {
  background: rgba(15, 23, 42, 0.55) !important;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.28);
  border-radius: 16px;
}

.portal-container[data-theme='glass-light'] .glass-panel {
  background: rgba(255, 255, 255, 0.68) !important;
  border: 1px solid rgba(0, 0, 0, 0.08) !important;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08);
}

@media (max-width: 1200px) {
  .portal-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 900px) {
  .portal-grid { grid-template-columns: repeat(2, 1fr); }
  .portal-top-bar { padding: 16px; }
  .user-copy { display: none; }
}
@media (max-width: 600px) {
  .portal-grid { grid-template-columns: 1fr; }
  .portal-title { letter-spacing: 2px; }
  .portal-subtitle { letter-spacing: 2px; font-size: 0.75rem; }
}
</style>
