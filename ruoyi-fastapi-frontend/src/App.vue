<template>
  <router-view />
</template>

<script setup>
import useSettingsStore from '@/store/modules/settings'
import { handleThemeStyle } from '@/utils/theme'

onMounted(() => {
  nextTick(() => {
    const settingsStore = useSettingsStore()
    // 初始化主题样式
    handleThemeStyle(settingsStore.theme)
    settingsStore.applyTheme()
  })
})
</script>
