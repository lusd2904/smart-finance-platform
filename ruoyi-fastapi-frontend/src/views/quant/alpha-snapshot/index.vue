<template>
  <div class="app-container alpha-snapshot-page">
    <div class="page-hero">
      <div>
        <h2>Alpha 因子快照</h2>
        <p>全市场日扫读模型 · Alpha101 / Alpha158 落库台账</p>
      </div>
      <div class="acts">
        <el-button type="primary" :loading="scanLoading" @click="handleScan" v-hasPermi="['quant:strategy:run']">立即日扫</el-button>
        <el-button @click="$router.push('/quant/factor')">因子分析</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="summary-row">
      <el-col :xs="12" :sm="6">
        <div class="sum-card">
          <div class="n">{{ snapshots.length }}</div>
          <div class="l">快照条数</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="sum-card">
          <div class="n">{{ overview.alpha101Total ?? '--' }}</div>
          <div class="l">Alpha101 覆盖</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="sum-card">
          <div class="n">{{ overview.alpha158Total ?? '--' }}</div>
          <div class="l">Alpha158 覆盖</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="sum-card">
          <div class="n muted">{{ overview.asOf || '--' }}</div>
          <div class="l">最近扫描 {{ overview.source || '读模型' }}</div>
        </div>
      </el-col>
    </el-row>

    <div v-if="hint" class="snap-hint">{{ hint }}</div>

    <el-card shadow="never">
      <template #header>
        <div class="panel-header">
          <span>因子快照列表</span>
          <el-radio-group v-model="limit" size="small" @change="loadSnapshots">
            <el-radio-button :label="40">40</el-radio-button>
            <el-radio-button :label="80">80</el-radio-button>
            <el-radio-button :label="120">120</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="snapshots" v-loading="loading" size="small" max-height="560">
        <el-table-column prop="symbol" label="标的" width="100"/>
        <el-table-column prop="market" label="市场" width="72"/>
        <el-table-column prop="total" label="综合分" width="88" align="right">
          <template #default="{ row }">{{ formatScore(row.total) }}</template>
        </el-table-column>
        <el-table-column prop="riskLevel" label="风险" width="88">
          <template #default="{ row }">
            <el-tag size="small" :type="riskTone(row.riskLevel)">{{ row.riskLevel || '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trendDirection" label="趋势" width="88"/>
        <el-table-column prop="alpha101Count" label="Alpha101" width="92" align="center"/>
        <el-table-column prop="alpha158Count" label="Alpha158" width="92" align="center"/>
        <el-table-column prop="asOf" label="快照日" width="110"/>
        <el-table-column prop="createTime" label="入库时间" min-width="160"/>
        <template #empty>
          <el-empty description="尚未生成 Alpha 因子快照，可点击「立即日扫」或等待定时任务" :image-size="72"/>
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="QuantAlphaSnapshot">
import { listFactorSnapshots, runDailyFactorScan, getReadmodelOverview } from '@/api/quant'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const scanLoading = ref(false)
const snapshots = ref([])
const limit = ref(80)
const hint = ref('')
const overview = ref({
  asOf: '',
  source: '',
  alpha101Total: null,
  alpha158Total: null
})

function formatScore(v) {
  if (v == null || v === '') return '--'
  const n = Number(v)
  return Number.isNaN(n) ? v : n.toFixed(1)
}

function riskTone(level) {
  const v = String(level || '').toLowerCase()
  if (v.includes('high') || v.includes('danger')) return 'danger'
  if (v.includes('medium') || v.includes('warn')) return 'warning'
  if (v.includes('low') || v.includes('safe')) return 'success'
  return 'info'
}

function applyOverview(data) {
  const factorScan = data?.factorScan || {}
  const items = factorScan.items || []
  overview.value = {
    asOf: factorScan.asOf || data?.refreshTime || '',
    source: data?.source === 'scheduled' ? '定时' : '实时',
    alpha101Total: items.length
      ? items.reduce((sum, it) => sum + Number(it.alpha101Count || 0), 0)
      : null,
    alpha158Total: items.length
      ? items.reduce((sum, it) => sum + Number(it.alpha158Count || 0), 0)
      : null
  }
}

async function loadSnapshots() {
  loading.value = true
  try {
    const res = await listFactorSnapshots(limit.value)
    snapshots.value = res.data || []
    if (snapshots.value.length) {
      hint.value = `已加载 ${snapshots.value.length} 条快照（最多 ${limit.value}）`
    } else {
      hint.value = '暂无落库快照 · 定时任务或手动日扫后会写入读模型'
    }
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  try {
    const res = await getReadmodelOverview()
    applyOverview(res.data || {})
  } catch {
    /* 读模型未就绪时保持空态 */
  }
}

async function load() {
  await Promise.all([loadSnapshots(), loadOverview()])
}

async function handleScan() {
  scanLoading.value = true
  try {
    const res = await runDailyFactorScan('balanced')
    const jobId = res.data && res.data.jobId
    if (jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队')
      const { pollMarketJob } = await import('@/api/market')
      const ticket = await pollMarketJob(jobId)
      if (ticket.status === 'failed') {
        proxy.$modal.msgError(ticket.error || '日扫失败')
        return
      }
    }
    proxy.$modal.msgSuccess(res.msg || '日扫完成')
    await load()
  } finally {
    scanLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)}
.page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap}
.summary-row{margin-bottom:12px}
.sum-card{background:var(--el-bg-color);border:1px solid var(--el-border-color-lighter);border-radius:10px;padding:14px 16px;text-align:center}
.sum-card .n{font-size:24px;font-weight:700;color:var(--text-emphasis)}
.sum-card .n.muted{font-size:14px;font-weight:600}
.sum-card .l{margin-top:6px;font-size:12px;color:var(--text-muted)}
.snap-hint{font-size:12px;color:var(--text-muted);margin:-4px 0 12px}
.panel-header{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
</style>
