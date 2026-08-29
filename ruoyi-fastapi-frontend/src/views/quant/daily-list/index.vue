<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>次日策略清单</h2>
        <p>收盘扫描生成本账户下一交易日标的。真实开仓走「量化交易 / 策略配置」里的本账户自动交易开关。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :loading="scanLoading" @click="handleScan" v-hasPermi="['quant:dailylist:scan']">扫描清单</el-button>
        <el-button type="success" :disabled="!canPlace" @click="handleOpen(false)" v-hasPermi="['quant:dailylist:open']">勾选开仓</el-button>
        <el-button :disabled="!canPlace" @click="handleOpen(true)" v-hasPermi="['quant:dailylist:auto']">开仓并加入持续清单</el-button>
        <el-button icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>
    <el-alert :title="accountHint" :type="tradeStatus.autoTradeEnabled ? 'info' : 'warning'" show-icon :closable="false" class="mb16" />
    <el-alert v-if="hint && hint !== accountHint" :title="hint" type="info" show-icon :closable="false" class="mb16" />
    <el-table v-loading="loading" :data="items" @selection-change="onSelect">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="代码" prop="symbol" width="110" />
      <el-table-column label="市场" prop="market" width="80" />
      <el-table-column label="名称" prop="name" width="140" />
      <el-table-column label="信号" prop="signal" width="80" />
      <el-table-column label="评分" prop="score" width="80" />
      <el-table-column label="置信度" prop="confidence" width="90" />
      <el-table-column label="状态" prop="status" width="110" />
      <el-table-column label="自动" width="80">
        <template #default="scope">{{ scope.row.autoTrade ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="理由" prop="reason" min-width="220" show-overflow-tooltip />
      <el-table-column label="失败原因" prop="error" min-width="160" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup name="QuantDailyListIndex">
import { getDailyList, scanDailyList, openDailyList } from '@/api/quant'
import { getAutoTradeStatus } from '@/api/trade'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const scanLoading = ref(false)
const list = ref({})
const items = ref([])
const selectedIds = ref([])
const tradeStatus = ref({ configured: false, autoTradeEnabled: false })

const hint = computed(() => {
  const row = list.value || {}
  return row.message || '交易日收盘后生成下一交易日清单；非交易日与空结果静默。'
})
const accountHint = computed(() => {
  if (!tradeStatus.value.configured) return '未配置长桥账户 Key，无法打开自动交易。请先到「量化交易 / 长桥配置」填写凭据。'
  if (!tradeStatus.value.autoTradeEnabled) return '本账户自动交易未开，清单不会向长桥下单。请到「量化交易 / 策略配置」打开开关。'
  return '本账户自动交易已开，勾选开仓将向长桥真实提交委托。'
})
const canPlace = computed(() => selectedIds.value.length && tradeStatus.value.autoTradeEnabled)

function onSelect(rows) {
  selectedIds.value = rows.map(r => r.itemId)
}

async function load() {
  loading.value = true
  try {
    const [listRes, statusRes] = await Promise.allSettled([getDailyList(), getAutoTradeStatus()])
    if (listRes.status === 'fulfilled') {
      const data = (listRes.value.data && listRes.value.data.list) || listRes.value.data || {}
      list.value = data
      items.value = data.items || []
    }
    if (statusRes.status === 'fulfilled') {
      tradeStatus.value = statusRes.value.data || { configured: false, autoTradeEnabled: false }
    }
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  scanLoading.value = true
  try {
    const res = await scanDailyList()
    proxy.$modal.msgSuccess(res.msg || '已提交扫描')
    await load()
  } finally {
    scanLoading.value = false
  }
}

function handleOpen(autoJoin) {
  if (!selectedIds.value.length) {
    proxy.$modal.msgWarning('请先勾选标的')
    return
  }
  if (!tradeStatus.value.configured) {
    proxy.$modal.msgWarning('未配置长桥账户 Key，无法打开自动交易')
    return
  }
  if (!tradeStatus.value.autoTradeEnabled) {
    proxy.$modal.msgWarning('请先在「量化交易 / 策略配置」打开本账户自动交易')
    return
  }
  openDailyList({ itemIds: selectedIds.value, autoJoin }).then(res => {
    proxy.$modal.msgSuccess(res.msg || '已提交')
    load()
  })
}

onMounted(load)
</script>

<style scoped lang="scss">
.page-hero {
  display: flex; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  h2 { margin: 0 0 4px; }
  p { margin: 0; color: #909399; font-size: 13px; max-width: 720px; }
}
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.mb16 { margin-bottom: 16px; }
</style>
