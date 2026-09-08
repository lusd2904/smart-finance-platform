<template>
  <el-dropdown trigger="click" popper-class="theme-switcher-popper" @command="handleCommand">
    <button type="button" class="theme-switcher" :class="{ compact }" aria-label="切换皮肤">
      <el-icon :size="compact ? 15 : 16"><Brush /></el-icon>
      <span v-if="!compact" class="theme-switcher__label">皮肤</span>
      <span class="theme-switcher__swatch" :style="{ background: themeMeta.preview }" aria-hidden="true"></span>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="theme in themes"
          :key="theme.id"
          :command="theme.id"
          class="theme-dropdown-item"
          :class="{ active: activeTheme === theme.id }"
        >
          <span class="theme-dropdown-item__swatch" :style="{ background: theme.preview }"></span>
          <span class="theme-dropdown-item__label">{{ theme.label }}</span>
          <el-icon v-if="activeTheme === theme.id" class="theme-dropdown-item__check" :size="14">
            <Check />
          </el-icon>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { Brush, Check } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme.js'

defineProps({
  compact: { type: Boolean, default: false }
})

const { themes, activeTheme, themeMeta, setTheme } = useTheme()
const handleCommand = (themeId) => setTheme(themeId)
</script>

<style scoped lang="scss">
.theme-switcher {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 36px;
  padding: 7px 10px;
  border: 1px solid color-mix(in srgb, var(--border-soft) 86%, transparent);
  border-radius: 12px;
  background: var(--surface-soft);
  color: var(--text-emphasis);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;

  &:hover,
  &:focus-visible {
    border-color: color-mix(in srgb, var(--accent) 28%, transparent);
    background: color-mix(in srgb, var(--surface-soft) 92%, transparent);
    transform: translateY(-1px);
    outline: none;
  }

  &.compact {
    width: 30px;
    height: 30px;
    padding: 0;
    border-radius: 8px;
  }
}

.theme-switcher__label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.theme-switcher__swatch,
.theme-dropdown-item__swatch {
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--text-emphasis) 34%, transparent);
}

.theme-switcher__swatch {
  width: 15px;
  height: 15px;
}

.theme-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 168px;

  &.active {
    color: var(--accent);
  }
}

.theme-dropdown-item__swatch {
  width: 16px;
  height: 16px;
}

.theme-dropdown-item__label {
  flex: 1;
  font-size: 12px;
}

.theme-dropdown-item__check {
  color: var(--accent);
}
</style>
