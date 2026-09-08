<template>
  <section class="placeholder-page">
    <div class="page-header glass-panel">
      <div class="page-title">
        <h2>{{ title }}</h2>
      </div>
    </div>
    <div class="glass-panel body">
      <p>即将上线</p>
      <div class="actions">
        <el-button type="primary" @click="$router.push('/index')">工作台</el-button>
        <el-button @click="$router.push('/trade/terminal')">行情交易</el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { placeholderMeta } from '@/config/menus'

const route = useRoute()
const title = computed(() => placeholderMeta[route.path]?.title || route.meta.title || '模块')
</script>

<style scoped lang="scss">
.placeholder-page {
  display: grid;
  gap: 10px;
}

.body {
  padding: 18px;
  display: grid;
  gap: 10px;
  color: var(--text-primary);
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
