<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>次日策略清单</h2>
        <p>收盘扫描生成下一交易日标的。勾选后一键长桥模拟开仓，禁止默认全开。加入量化后按清单持续模拟交易。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :loading="scanLoading" @click="handleScan" v-hasPermi="['quant:dailylist:scan']">扫描清单</el-button>
        <el-button type="success" :disabled="!selectedIds.length" @click="handleOpen(false)" v-hasPermi="['quant:dailylist:open']">勾选模拟开仓</el-button>
        <el-button @click="handleOpen(true)" :disabled="!selectedIds.length" v-hasPermi="['quant:dailylist:auto']">开仓并持续自动交易</el-button>
        <el-button @click="toggleAuto" v-hasPermi="['quant:dailylist:auto']">{{ list.autoEnabled ? '暂停自动交易' : '启用自动交易' }}</el-button>
        <el-button icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>
    <el-alert :title="hint" type="info" show-icon :closable="false" class="mb16" />
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
import { getDailyList, scanDailyList, openDailyList, setDailyListAuto } from '@/api/quant'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const scanLoading = ref(false)
const list = ref({})
const items = ref([])
const selectedIds = ref([])

const hint = computed(() => {
  const row = list.value || {}
  return row.message || '交易日收盘后生成下一交易日清单；非交易日与空结果静默。'
})

function onSelect(rows) {
  selectedIds.value = rows.map(r => r.itemId)
}

async function load() {
  loading.value = true
  try {
    const res = await getDailyList()
    const data = (res.data && res.data.list) || res.data || {}
    list.value = data
    items.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  scanLoading.value = true
  try {
    const res = await scanDailyList({ profile: 'balanced' })
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
  openDailyList({ itemIds: selectedIds.value, autoJoin }).then(res => {
    proxy.$modal.msgSuccess(res.msg || '已提交')
    load()
  })
}

function toggleAuto() {
  setDailyListAuto({ enabled: !list.value.autoEnabled, itemIds: selectedIds.value }).then(() => {
    proxy.$modal.msgSuccess('已更新')
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
