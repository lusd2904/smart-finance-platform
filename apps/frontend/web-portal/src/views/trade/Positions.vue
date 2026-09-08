<template>
  <PageFrame title="持仓" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无持仓">
        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="symbolName" label="名称" min-width="140" />
        <el-table-column prop="quantity" label="数量" width="100" align="right" />
        <el-table-column prop="availableQuantity" label="可用" width="100" align="right" />
        <el-table-column prop="costPrice" label="成本价" width="100" align="right" />
        <el-table-column label="现价" width="100" align="right">
          <template #default="{ row }">{{ fmtPx(row.last ?? row.price) }}</template>
        </el-table-column>
        <el-table-column label="涨跌%" width="90" align="right">
          <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span></template>
        </el-table-column>
        <el-table-column label="浮盈%" width="90" align="right">
          <template #default="{ row }"><span :class="changeClass(row.pnlPct ?? row.unrealizedPnlRate)">{{ fmtChange(row.pnlPct ?? row.unrealizedPnlRate) }}</span></template>
        </el-table-column>
        <el-table-column prop="currency" label="币种" width="80" />
        <el-table-column width="80">
          <template #default>
            <el-button link type="primary" @click="$router.push('/trade/terminal')">交易</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getTradePositions } from '@/api/trade'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await getTradePositions())
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
