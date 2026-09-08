<template>
  <aside class="sidebar" :class="{ collapsed: isCollapsed }">
    <div class="sidebar-shell">
      <button type="button" class="logo" @click="router.push('/index')">
        <div class="logo-icon">
          <el-icon size="22"><TrendCharts /></el-icon>
        </div>
        <div class="logo-copy" v-show="!isCollapsed">
          <strong>智慧金融</strong>
        </div>
      </button>

      <nav class="menu">
        <div v-for="subsystem in menuTree" :key="subsystem.code" class="subsystem-block">
          <button
            type="button"
            class="subsystem-item"
            :class="{ expanded: isExpanded(subsystem.code), active: isSubsystemActive(subsystem) }"
            @click="handleSubsystemClick(subsystem)"
          >
            <div class="subsystem-main">
              <div class="subsystem-icon">
                <el-icon size="18"><component :is="subsystem.icon" /></el-icon>
              </div>
              <span v-show="!isCollapsed" class="subsystem-title">{{ subsystem.title }}</span>
            </div>
            <el-icon v-show="!isCollapsed && subsystem.groups.length" class="subsystem-arrow" size="14">
              <ArrowDown v-if="isExpanded(subsystem.code)" />
              <ArrowRight v-else />
            </el-icon>
          </button>

          <div v-if="!isCollapsed && isExpanded(subsystem.code) && subsystem.groups.length" class="submenu-list">
            <section v-for="group in subsystem.groups" :key="`${subsystem.code}:${group.code}`" class="group-block">
              <button
                v-for="item in group.items"
                :key="item.path"
                type="button"
                class="submenu-item"
                :class="{ active: isRouteActive(item.path) }"
                @click="router.push(item.path)"
              >
                <el-icon size="16"><component :is="item.icon" /></el-icon>
                <span class="menu-text">{{ item.title }}</span>
              </button>
            </section>
          </div>
        </div>
      </nav>

      <div class="sidebar-foot">
        <button type="button" class="collapse-btn" @click="toggleCollapse">
          <el-icon size="18">
            <Fold v-if="!isCollapsed" />
            <Expand v-else />
          </el-icon>
          <span v-show="!isCollapsed">收起导航</span>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, ArrowRight, Expand, Fold, TrendCharts } from '@element-plus/icons-vue'
import { menuTree } from '@/config/menus'

const route = useRoute()
const router = useRouter()
const isCollapsed = ref(false)
const expandedSubsystems = ref(['workspace', 'market', 'trade'])

const isRouteActive = (path) => {
  const active = route.meta.activeMenu || route.path
  return active === path || route.path === path
}

const isSubsystemActive = (subsystem) => {
  if (subsystem.path && isRouteActive(subsystem.path)) return true
  return subsystem.groups.some((g) => g.items.some((item) => isRouteActive(item.path)))
}

const isExpanded = (code) => expandedSubsystems.value.includes(code)

const handleSubsystemClick = (subsystem) => {
  if (!subsystem.groups.length) {
    router.push(subsystem.path)
    return
  }
  if (isCollapsed.value) {
    router.push(subsystem.path)
    return
  }
  if (isExpanded(subsystem.code)) {
    expandedSubsystems.value = expandedSubsystems.value.filter((c) => c !== subsystem.code)
  } else {
    expandedSubsystems.value = [...expandedSubsystems.value, subsystem.code]
  }
}

const syncSidebarWidth = () => {
  document.documentElement.style.setProperty('--sidebar-width', isCollapsed.value ? '72px' : '248px')
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sfp-sidebar-collapsed', String(isCollapsed.value))
  syncSidebarWidth()
}

watch(
  () => route.fullPath,
  () => {
    const active = menuTree.filter((item) => isSubsystemActive(item)).map((item) => item.code)
    expandedSubsystems.value = Array.from(new Set([...expandedSubsystems.value, ...active]))
  },
  { immediate: true }
)

onMounted(() => {
  isCollapsed.value = localStorage.getItem('sfp-sidebar-collapsed') === 'true'
  syncSidebarWidth()
})
</script>

<style scoped lang="scss">
.sidebar {
  position: relative;
  z-index: 1200;
  width: var(--sidebar-width, 248px);
  transition: width 0.28s ease;

  &.collapsed {
    .logo, .collapse-btn, .subsystem-item, .submenu-item {
      justify-content: center;
    }
    .submenu-list, .subsystem-arrow { display: none; }
  }
}

.sidebar-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  background: var(--chrome-surface);
  backdrop-filter: var(--chrome-backdrop);
  -webkit-backdrop-filter: var(--chrome-backdrop);
  border-right: 1px solid var(--border-soft);
  box-shadow: var(--sidebar-shadow), var(--chrome-inset);
  overflow: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 16px 20px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  border-bottom: 1px solid var(--border-soft);
}

.logo-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #06121d;
  background:
    radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.68), transparent 28%),
    linear-gradient(135deg, var(--accent), var(--accent-strong));
  box-shadow: 0 14px 28px color-mix(in srgb, var(--accent-strong) 18%, transparent);
}

.logo-copy strong {
  font-size: 15px;
  color: var(--text-emphasis);
}

.menu {
  flex: 1;
  padding: 8px 6px 10px;
  overflow-y: auto;
}

.subsystem-item,
.submenu-item,
.collapse-btn {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: 8px;
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}

.subsystem-main {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  flex: 1;
}

.subsystem-icon {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  color: var(--text-emphasis);
}

.subsystem-title {
  color: var(--text-emphasis);
  font-size: 15px;
  font-weight: 500;
}

.submenu-list {
  display: grid;
  gap: 4px;
  margin: 3px 0 3px 12px;
  padding: 3px 0 3px 10px;
  border-left: 1px solid color-mix(in srgb, var(--accent-strong) 9%, transparent);
}

.submenu-item {
  font-size: 13px;
}

.subsystem-item:hover,
.submenu-item:hover,
.submenu-item.active,
.collapse-btn:hover,
.subsystem-item.active {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent) 12%, transparent),
    color-mix(in srgb, var(--surface-soft) 72%, transparent)
  );
  color: var(--text-emphasis);
}

.sidebar-foot {
  padding: 8px 6px 10px;
}

.collapse-btn {
  justify-content: center;
  background: color-mix(in srgb, var(--surface-soft) 56%, var(--surface-emphasis) 44%);
  color: var(--text-emphasis);
}

@media (max-width: 760px) {
  .sidebar { width: 72px; }
  .sidebar .logo-copy,
  .sidebar .subsystem-title,
  .sidebar .menu-text,
  .sidebar .subsystem-arrow,
  .sidebar .collapse-btn span,
  .sidebar .submenu-list { display: none; }
}
</style>
