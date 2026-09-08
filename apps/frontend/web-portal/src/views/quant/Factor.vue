<template>
  <PageFrame title="因子分析" subtitle="因子快照 · 定义 · 对齐现网 /quant/factor" badge="「因子分析 /quant/factor」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <template #header><h3>因子快照</h3></template>
      <el-table :data="snapshots" stripe empty-text="暂无快照">
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="score" label="得分" width="80" align="right" />
        <el-table-column prop="asOf" label="日期" width="120" />
      </el-table>
    </el-card>
    <el-card shadow="never" class="glass-panel">
      <template #header><h3>因子定义</h3></template>
      <el-table :data="schema" stripe empty-text="暂无定义">
        <el-table-column prop="code" label="代码" width="140" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="family" label="族" width="120" />
        <el-table-column prop="desc" label="说明" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getFactorSchema, listFactorSnapshots } from '@/api/quant'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const snapshots = ref([])
const schema = ref([])

async function load() {
  loading.value = true
  try {
    const [s, f] = await Promise.allSettled([listFactorSnapshots(), getFactorSchema()])
    if (s.status === 'fulfilled') snapshots.value = unwrapList(s.value)
    if (f.status === 'fulfilled') {
      const data = unwrap(f.value)
      schema.value = data.factors || data.items || unwrapList(f.value)
    }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
</style>
