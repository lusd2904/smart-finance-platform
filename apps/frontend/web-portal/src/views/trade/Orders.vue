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
        <el-table-column prop="quantity" label="数量" width="90" align="right" />
        <el-table-column prop="price" label="价格" width="90" align="right" />
        <el-table-column prop="executedQuantity" label="成交量" width="90" align="right" />
        <el-table-column prop="updatedAt" label="更新" min-width="150" />
        <el-table-column width="80">
          <template #default="{ row }">
            <el-button v-if="scope === 'today' && row.orderId" link type="danger" @click="cancel(row)">撤单</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { cancelTradeOrder, getTradeOrders } from '@/api/trade'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const scope = ref('today')
const list = ref([])

async function load() {
  loading.value = true
  try {
    list.value = unwrapList(await getTradeOrders(scope.value))
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function cancel(row) {
  try {
    await cancelTradeOrder(row.orderId)
    ElMessage.success('已撤单')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '撤单失败')
  }
}

onMounted(load)
</script>
