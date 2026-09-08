<template>
  <section class="placeholder-page">
    <div class="page-header glass-panel">
      <div class="page-title">
        <h2>{{ title }}</h2>
      </div>
    </div>
    <div class="glass-panel body">
      <p>该模块属于 SFP 现有信息架构，将在工作台 / 行情交易验证通过后再迁入本门户。</p>
      <p class="hint">当前请继续使用旧前端 <code>ruoyi-fastapi-frontend</code> 访问完整功能。本目录不会覆盖其 dist。</p>
      <div class="actions">
        <el-button type="primary" @click="$router.push('/index')">返回工作台</el-button>
        <el-button @click="$router.push('/trade/terminal')">打开行情交易</el-button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { placeholderMeta } from '@/config/menus'

const route = useRoute()
const title = computed(() => placeholderMeta[route.path]?.title || route.meta.title || '模块迁移中')
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

.hint {
  color: var(--text-secondary);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
