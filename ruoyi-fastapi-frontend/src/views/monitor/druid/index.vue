<template>
  <div class="app-container druid-page">
    <el-empty v-if="!available" :description="emptyText">
      <p class="hint">当前环境未启用阿里 Druid 数据源监控控制台（未部署 / 未配置）。</p>
    </el-empty>
    <i-frame v-else v-model:src="url"></i-frame>
  </div>
</template>

<script setup name="MonitorDruid">
import iFrame from '@/components/iFrame'

const url = ref(import.meta.env.VITE_APP_BASE_API + '/druid/login.html')
const available = ref(false)
const emptyText = ref('Druid 未部署 / 未配置')

async function probe() {
  const enabled = String(import.meta.env.VITE_APP_DRUID_ENABLED || '').toLowerCase()
  if (enabled === 'true' || enabled === '1') {
    available.value = true
    return
  }
  try {
    const resp = await fetch(url.value, { method: 'GET', credentials: 'omit' })
    if (resp.ok) {
      available.value = true
      return
    }
  } catch (e) {
    /* not deployed */
  }
  available.value = false
  emptyText.value = 'Druid 未部署 / 未配置'
}

onMounted(probe)
</script>

<style scoped>
.hint {
  margin-top: 8px;
  color: var(--text-muted, #909399);
  font-size: 13px;
}
</style>
