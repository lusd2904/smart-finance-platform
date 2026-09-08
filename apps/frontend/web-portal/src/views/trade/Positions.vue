<template>
  <PageFrame title="持仓" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-alert v-if="msg" :title="msg" type="info" show-icon :closable="false" />
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无持仓">
        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="symbolName" label="名称" min-width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="availableQuantity" label="可用" width="100" />
        <el-table-column prop="costPrice" label="成本价" width="100" />
        <el-table-column label="现价" width="100">
          <template #default="{ row }">{{ fmtNum(row.last ?? row.currentPrice) }}</template>
        </el-table-column>
        <el-table-column label="涨跌%" width="90">
          <template #default="{ row }"><span :class="changeClass(row.changePct)">{{ fmtChange(row.changePct) }}</span></template>
        </el-table-column>
        <el-table-column label="浮盈%" width="90">
          <template #default="{ row }"><span :class="changeClass(row.pnlPct ?? row.pnlRate)">{{ fmtChange(row.pnlPct ?? row.pnlRate) }}</span></template>
        </el-table-column>
        <el-table-column prop="currency" label="币种" width="80" />
        <el-table-column width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(terminalRoute(posPair(row)))">交易</el-button>
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
import { changeClass, fmtChange, fmtNum } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'

const loading = ref(false)
const list = ref([])
const msg = ref('')

function posPair(row) {
  const raw = String((row && row.symbol) || '').toUpperCase()
  let market = String((row && row.market) || 'US').toUpperCase()
  let symbol = raw
  if (raw.endsWith('.US')) { symbol = raw.slice(0, -3); market = 'US' }
  else if (raw.endsWith('.HK')) { symbol = raw.slice(0, -3); market = 'HK' }
  else if (raw.endsWith('.SH') || raw.endsWith('.SZ') || raw.endsWith('.SS')) { symbol = raw.split('.')[0]; market = 'CN' }
  return { symbol, market }
}

async function load() {
  loading.value = true
  try {
    const res = await getTradePositions()
    const d = unwrap(res)
    list.value = d.positions || unwrapList(res)
    msg.value = d.message || (d.configured === false ? '未配置长桥凭证' : '')
  } catch {
    list.value = []
    msg.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
