<template>
  <PageFrame title="委托" :loading="loading">
    <template #actions>
      <el-radio-group v-model="scope" @change="load">
        <el-radio-button value="today">今日</el-radio-button>
        <el-radio-button value="history">历史</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无委托">
        <el-table-column prop="orderId" label="订单号" width="180" />
        <el-table-column prop="symbol" label="标的" width="110" />
        <el-table-column prop="side" label="方向" width="80" />
        <el-table-column prop="orderType" label="类型" width="90" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ row.statusLabel || row.status || '--' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="90" />
        <el-table-column prop="price" label="价格" width="90" />
        <el-table-column prop="executedQuantity" label="成交量" width="90" />
        <el-table-column prop="executedPrice" label="成交价" width="90" />
        <el-table-column prop="updatedAt" label="更新" min-width="150" />
        <el-table-column width="88">
          <template #default="{ row }">
            <el-button v-if="row.orderId && scope === 'today' && orderLooksOpen(row)" link type="danger" @click="cancel(row)">撤单</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { cancelTradeOrder, getTradeOrders } from '@/api/trade'
import { unwrap, unwrapList } from '@/utils/list'

const OPEN_STATUS = new Set(['submitted', 'new', 'wait_to_new', 'waittonew', 'partial_filled', 'partialfilled', 'wait_to_cancel', 'waittocancel', 'pending', 'partial', 'open', 'not_reported', 'notreported'])
const OPEN_LABEL = new Set(['已提交', '待成交', '待报', '待撤', '部分成交'])

const loading = ref(false)
const scope = ref('today')
const list = ref([])

function orderLooksOpen(row) {
  if (!row) return false
  if (row.open === true) return true
  const status = String(row.status || '').trim()
  const compact = status.toLowerCase().replace(/[\s-]/g, '_')
  if (OPEN_STATUS.has(compact) || OPEN_STATUS.has(compact.replace(/_/g, ''))) return true
  return OPEN_LABEL.has(String(row.statusLabel || '').trim())
}

async function load() {
  loading.value = true
  try {
    const res = await getTradeOrders(scope.value)
    const d = unwrap(res)
    list.value = d.orders || unwrapList(res)
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function cancel(row) {
  await ElMessageBox.confirm(`确认撤单 ${row.orderId}？`, '委托')
  const res = await cancelTradeOrder(row.orderId)
  const d = res.data || {}
  if (d.ok !== false) ElMessage.success(d.message || '已撤')
  else ElMessage.error(d.message || '失败')
  load()
}

onMounted(load)
</script>
