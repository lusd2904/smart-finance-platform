<template>
  <div class="app-container scan-runs">
    <div class="toolbar">
      <el-space wrap>
        <el-tag type="info">只读台账</el-tag>
        <span>最近</span>
        <el-radio-group v-model="limit" size="small" @change="loadList">
          <el-radio-button :label="20">20</el-radio-button>
          <el-radio-button :label="50">50</el-radio-button>
          <el-radio-button :label="100">100</el-radio-button>
        </el-radio-group>
        <el-button icon="Refresh" @click="loadList">刷新</el-button>
      </el-space>
    </div>

    <el-row :gutter="12" class="mb16 summary-row">
      <el-col :span="6"><div class="sum-card"><div class="n">{{ summary.recordCount ?? 0 }}</div><div class="l">记录数</div></div></el-col>
      <el-col :span="6"><div class="sum-card"><div class="n">{{ summary.completedCount ?? 0 }}</div><div class="l">已完成</div></div></el-col>
      <el-col :span="6"><div class="sum-card"><div class="n">{{ summary.opportunityCount ?? 0 }}</div><div class="l">有机会</div></div></el-col>
      <el-col :span="6"><div class="sum-card"><div class="n">{{ summary.submittedCount ?? 0 }}</div><div class="l">已提交</div></div></el-col>
    </el-row>

    <el-table v-loading="loading" :data="list" style="width: 100%" @expand-change="onExpand">
      <el-table-column type="expand">
        <template #default="scope">
          <div class="expand-box" v-loading="detailLoading[scope.row.runId]">
            <template v-if="details[scope.row.runId]">
              <el-row :gutter="12">
                <el-col :md="8" :xs="24">
                  <div class="sub-title">机会标的</div>
                  <el-table :data="details[scope.row.runId].opportunities || []" size="small">
                    <el-table-column prop="symbol" label="代码" width="90" />
                    <el-table-column prop="side" label="方向" width="70" />
                    <el-table-column prop="confidence" label="置信度" width="80" />
                    <el-table-column prop="reason" label="理由" show-overflow-tooltip />
                  </el-table>
                </el-col>
                <el-col :md="8" :xs="24">
                  <div class="sub-title">候选快照（最多12）</div>
                  <el-table :data="details[scope.row.runId].candidates || []" size="small">
                    <el-table-column prop="symbol" label="代码" width="90" />
                    <el-table-column prop="riskLevel" label="风险" width="70" />
                    <el-table-column prop="confidence" label="置信度" width="80" />
                    <el-table-column prop="reason" label="理由" show-overflow-tooltip />
                  </el-table>
                </el-col>
                <el-col :md="8" :xs="24">
                  <div class="sub-title">跳过与控制</div>
                  <el-descriptions :column="1" size="small" border>
                    <el-descriptions-item label="策略档位">{{ details[scope.row.runId].strategyProfile }}</el-descriptions-item>
                    <el-descriptions-item label="纸账户">是（当前不自动下单）</el-descriptions-item>
                    <el-descriptions-item label="跳过数">{{ details[scope.row.runId].skippedCount }}</el-descriptions-item>
                  </el-descriptions>
                  <el-table :data="(details[scope.row.runId].skipped || []).slice(0, 8)" size="small" style="margin-top: 8px">
                    <el-table-column prop="symbol" label="代码" width="90" />
                    <el-table-column prop="skipReason" label="跳过原因" show-overflow-tooltip />
                  </el-table>
                </el-col>
              </el-row>
            </template>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="运行ID" prop="runId" width="90" />
      <el-table-column label="批次" prop="cycleId" width="160" show-overflow-tooltip />
      <el-table-column label="启动时间" prop="startedAt" width="170" />
      <el-table-column label="状态" prop="status" width="100">
        <template #default="scope">
          <el-tag size="small">{{ statusLabel(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="原因" prop="reason" width="120">
        <template #default="scope">{{ reasonLabel(scope.row.reason) }}</template>
      </el-table-column>
      <el-table-column label="标的/评估/机会" width="140" align="center">
        <template #default="scope">{{ scope.row.targetCount }}/{{ scope.row.evaluatedCount }}/{{ scope.row.opportunityCount }}</template>
      </el-table-column>
      <el-table-column label="档位" prop="strategyProfile" width="110" />
      <el-table-column label="说明" prop="message" min-width="200" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup name="QuantScanRunsIndex">
import { listScanRuns, getScanRunDetail } from '@/api/quant'

const loading = ref(false)
const list = ref([])
const summary = ref({})
const limit = ref(20)
const details = ref({})
const detailLoading = ref({})

function statusLabel(s) {
  return { completed: '已完成', running: '运行中', failed: '失败', skipped: '已跳过' }[s] || s || '--'
}
function reasonLabel(r) {
  return {
    executed: '已执行',
    no_opportunity: '无机会',
    off_hours: '非交易时段',
    disabled: '开关关闭',
    failed: '执行失败'
  }[r] || r || '--'
}

function loadList() {
  loading.value = true
  listScanRuns({ limit: limit.value })
    .then(res => {
      const data = res.data || {}
      list.value = data.items || []
      summary.value = data.summary || {}
    })
    .finally(() => {
      loading.value = false
    })
}

function onExpand(row, expandedRows) {
  const open = expandedRows.some(r => r.runId === row.runId)
  if (!open || details.value[row.runId]) return
  detailLoading.value[row.runId] = true
  getScanRunDetail(row.cycleId || row.runId)
    .then(res => {
      details.value[row.runId] = res.data || {}
    })
    .finally(() => {
      detailLoading.value[row.runId] = false
    })
}

onMounted(loadList)
</script>

<style lang="scss" scoped>
.scan-runs {
  .toolbar {
    margin-bottom: 12px;
  }
  .sum-card {
    background: var(--el-fill-color-light);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
    .n {
      font-size: 22px;
      font-weight: 700;
    }
    .l {
      font-size: 12px;
      color: #909399;
      margin-top: 4px;
    }
  }
  .expand-box {
    padding: 8px 12px 16px;
  }
  .sub-title {
    font-weight: 600;
    margin-bottom: 8px;
  }
  .mb16 {
    margin-bottom: 16px;
  }
}
</style>
