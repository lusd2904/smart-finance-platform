<template>
  <div class="app-container ai-trade-runs-container">
    <!-- 头部横幅与操作 -->
    <div class="page-hero">
      <div class="hero-left">
        <div class="hero-tags">
          <el-tag effect="dark" type="primary">长桥自选股票池</el-tag>
          <el-tag effect="plain" type="success">美股开盘量化扫描</el-tag>
          <el-tag :type="statusData.guardrails?.requirePaper ? 'warning' : 'danger'" effect="plain">
            {{ statusData.guardrails?.requirePaper ? '纸账户保护：仅扫描' : '纸账户保护已关闭' }}
          </el-tag>
          <el-tag :type="statusData.submitAllowed ? 'danger' : 'info'" effect="plain">
            {{ statusData.submitAllowed ? '允许自动委托' : (statusData.submitBlockReason || '默认不下单') }}
          </el-tag>
        </div>
        <h2>AI 自动交易与日内风控台账</h2>
        <p>默认只扫描自选池。自动委托需关闭服务端纸账户保护并打开长桥交易开关。</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :icon="VideoPlay" :loading="triggering" @click="handleTriggerRun(false)" v-hasPermi="['trade:aitrade:run']">
          扫描（不下单）
        </el-button>
        <el-button type="danger" plain :loading="triggering" @click="handleTriggerRun(true)" v-hasPermi="['trade:aitrade:run']">
          扫描并尝试下单
        </el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 核心日内护栏与指标卡片 -->
    <el-row :gutter="16" class="metric-row">
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-label">日内委托笔数</div>
          <div class="metric-val">
            <strong>{{ statusData.guardrails?.todayOrdersCount || 0 }}</strong>
            <span>/ {{ statusData.guardrails?.maxDailyOrders || 10 }} 笔</span>
          </div>
          <el-progress
            :percentage="Math.min(100, Math.round(((statusData.guardrails?.todayOrdersCount || 0) / (statusData.guardrails?.maxDailyOrders || 10)) * 100))"
            :status="statusData.guardrails?.isOrderLimitReached ? 'exception' : ''"
            :stroke-width="6"
          />
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-label">日内买入金额</div>
          <div class="metric-val">
            <strong>${{ (statusData.guardrails?.todayNotionalAmount || 0).toLocaleString() }}</strong>
            <span>/ ${{ (statusData.guardrails?.maxDailyNotionalAmount || 6000).toLocaleString() }}</span>
          </div>
          <el-progress
            :percentage="Math.min(100, Math.round(((statusData.guardrails?.todayNotionalAmount || 0) / (statusData.guardrails?.maxDailyNotionalAmount || 6000)) * 100))"
            :status="statusData.guardrails?.isAmountLimitReached ? 'exception' : 'success'"
            :stroke-width="6"
          />
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-label">累计扫描周期数</div>
          <div class="metric-val">
            <strong>{{ runList.length }}</strong>
            <span>次</span>
          </div>
          <div class="metric-sub">最近执行: {{ runList[0]?.startedAt || '--' }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <div class="metric-card">
          <div class="metric-label">累计发现机会 / 委托</div>
          <div class="metric-val">
            <strong class="text-success">{{ totalOpportunities }}</strong>
            <span>/ {{ totalOrders }} 笔</span>
          </div>
          <div class="metric-sub">执行策略: 均衡型 (Balanced)</div>
        </div>
      </el-col>
    </el-row>

    <!-- 台账全景列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>扫描台账记录历史</span>
          <el-select v-model="limit" size="small" style="width: 120px" @change="loadData">
            <el-option label="最近 20 条" :value="20" />
            <el-option label="最近 50 条" :value="50" />
            <el-option label="最近 100 条" :value="100" />
          </el-select>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="runList"
        row-key="cycleId"
        stripe
        style="width: 100%"
        empty-text="暂无 AI 自动交易扫描台账"
      >
        <!-- 展开行查看详细快照 -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-wrapper">
              <!-- 机会标的 -->
              <div class="expand-section">
                <div class="section-title">
                  <span class="dot green"></span>
                  <strong>机会标的与决策 ({{ (row.opportunitiesSnapshot || []).length }})</strong>
                </div>
                <div v-if="(row.opportunitiesSnapshot || []).length" class="opp-grid">
                  <div
                    v-for="(opp, idx) in row.opportunitiesSnapshot"
                    :key="idx"
                    class="opp-item"
                  >
                    <div class="opp-top">
                      <span class="opp-sym">{{ opp.symbol }}</span>
                      <el-tag size="small" :type="opp.signal === 'BUY' ? 'success' : 'danger'">
                        {{ opp.signal }}
                      </el-tag>
                      <span class="opp-conf">置信度: {{ opp.confidence }}%</span>
                    </div>
                    <div class="opp-reason">{{ opp.reason || '综合多因子评分达标' }}</div>
                  </div>
                </div>
                <div v-else class="empty-hint">本次周期未出现达标的机会标的</div>
              </div>

              <!-- 拦截与跳过原因 -->
              <div class="expand-section">
                <div class="section-title">
                  <span class="dot orange"></span>
                  <strong>风控护栏拦截与跳过明细 ({{ (row.skippedReasons || []).length }})</strong>
                </div>
                <div v-if="(row.skippedReasons || []).length" class="skip-grid">
                  <div
                    v-for="(sk, idx) in row.skippedReasons"
                    :key="idx"
                    class="skip-item"
                  >
                    <span class="skip-sym">{{ sk.symbol }}</span>
                    <span class="skip-text">{{ sk.reason }}</span>
                  </div>
                </div>
                <div v-else class="empty-hint">无风控拦截记录</div>
              </div>

              <!-- 护栏快照 -->
              <div class="expand-section">
                <div class="section-title">
                  <span class="dot blue"></span>
                  <strong>执行时日内护栏快照</strong>
                </div>
                <div class="guardrail-badges">
                  <el-tag size="small" effect="plain">单标的上限: ${{ row.guardrailSnapshot?.maxAmountPerSymbol || 2000 }}</el-tag>
                  <el-tag size="small" effect="plain">最多标的: {{ row.guardrailSnapshot?.maxSymbols || 3 }} 只</el-tag>
                  <el-tag size="small" effect="plain">实时价滑点容忍: {{ ((row.guardrailSnapshot?.priceSlippageTolerance || 0.03) * 100).toFixed(0) }}%</el-tag>
                  <el-tag size="small" effect="plain">当时已下单: {{ row.guardrailSnapshot?.todayOrdersCount || 0 }} 笔</el-tag>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="cycleId" label="周期标识" min-width="170">
          <template #default="{ row }">
            <code class="cycle-code">{{ row.cycleId }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="strategyProfile" label="策略档位" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ profileLabel(row.strategyProfile) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="targetCount" label="扫描标的" width="90" align="center" />
        <el-table-column prop="evaluatedCount" label="已评估" width="80" align="center" />
        <el-table-column prop="opportunityCount" label="发现机会" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.opportunityCount > 0 ? 'text-success font-bold' : ''">
              {{ row.opportunityCount }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="submittedOrdersCount" label="提交委托" width="90" align="center">
          <template #default="{ row }">
            <span :class="row.submittedOrdersCount > 0 ? 'text-primary font-bold' : ''">
              {{ row.submittedOrdersCount }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="运行摘要" min-width="260" show-overflow-tooltip />
        <el-table-column prop="startedAt" label="执行时间" width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="TradeAiRuns">
import { ref, computed, onMounted } from 'vue'
import { VideoPlay, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAiTradeRuns, getAutoTradeStatus, runAutoTrade } from '@/api/trade'
import { getReadmodelOverview } from '@/api/quant'

const loading = ref(false)
const triggering = ref(false)
const limit = ref(30)
const runList = ref([])
const statusData = ref({})

const totalOpportunities = computed(() => {
  return runList.value.reduce((acc, cur) => acc + (cur.opportunityCount || 0), 0)
})

const totalOrders = computed(() => {
  return runList.value.reduce((acc, cur) => acc + (cur.submittedOrdersCount || 0), 0)
})

function profileLabel(profile) {
  const map = {
    conservative: '保守型',
    balanced: '均衡型',
    aggressive: '激进型'
  }
  return map[profile] || profile || '均衡型'
}

async function loadData() {
  loading.value = true
  try {
    const [runsRes, statusRes] = await Promise.allSettled([
      listAiTradeRuns(limit.value),
      getAutoTradeStatus()
    ])
    if (runsRes.status === 'fulfilled') {
      runList.value = runsRes.value.data || []
    }
    if (statusRes.status === 'fulfilled') {
      statusData.value = statusRes.value.data || {}
    }
    const overviewRes = await getReadmodelOverview().catch(() => null)
    if (overviewRes?.data?.asset) {
      statusData.value = { ...statusData.value, readModel: overviewRes.data }
    }
  } catch (err) {
    ElMessage.error('加载自动交易台账失败: ' + err.message)
  } finally {
    loading.value = false
  }
}

async function handleTriggerRun(execute = false) {
  try {
    if (execute) {
      await ElMessageBox.confirm(
        '将按服务端护栏尝试向券商提交委托。纸账户保护开启或交易开关关闭时仍不会下单。确认继续？',
        '二次确认',
        { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' }
      )
    }
  } catch {
    return
  }
  triggering.value = true
  try {
    const res = await runAutoTrade({ strategyProfile: 'balanced', execute: Boolean(execute) })
    ElMessage.success(res.msg || (execute ? '扫描完成（已按护栏决定是否下单）' : '扫描完成，未下单'))
    await loadData()
  } catch (err) {
    ElMessage.error('触发自动交易扫描失败: ' + err.message)
  } finally {
    triggering.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.ai-trade-runs-container {
  padding: 16px;
}

.page-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--el-bg-color-overlay, #1a1f2c);
  border: 1px solid var(--el-border-color-lighter, #2d3748);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
}

.hero-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.hero-left h2 {
  margin: 0 0 6px;
  font-size: 20px;
  color: var(--el-text-color-primary, #ffffff);
}

.hero-left p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.metric-row {
  margin-bottom: 16px;
}

.metric-card {
  background: var(--el-bg-color-overlay, #1a1f2c);
  border: 1px solid var(--el-border-color-lighter, #2d3748);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 8px;
}

.metric-label {
  font-size: 13px;
  color: var(--el-text-color-secondary, #94a3b8);
  margin-bottom: 6px;
}

.metric-val {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 10px;
}

.metric-val strong {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary, #ffffff);
}

.metric-val span {
  font-size: 12px;
  color: var(--el-text-color-secondary, #64748b);
}

.metric-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary, #64748b);
}

.table-card {
  background: var(--el-bg-color-overlay, #1a1f2c);
  border: 1px solid var(--el-border-color-lighter, #2d3748);
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.cycle-code {
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

.text-success {
  color: #10b981;
}

.text-primary {
  color: #3b82f6;
}

.font-bold {
  font-weight: 700;
}

.expand-wrapper {
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 13px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.green { background: #10b981; }
.dot.orange { background: #f59e0b; }
.dot.blue { background: #3b82f6; }

.opp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}

.opp-item {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: 6px;
  padding: 8px 12px;
}

.opp-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.opp-sym {
  font-weight: 700;
}

.opp-conf {
  font-size: 12px;
  color: #10b981;
  margin-left: auto;
}

.opp-reason {
  font-size: 12px;
  color: var(--el-text-color-secondary, #94a3b8);
}

.skip-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skip-item {
  font-size: 12px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  padding: 4px 8px;
  border-radius: 4px;
  display: flex;
  gap: 8px;
}

.skip-sym {
  font-weight: 600;
  color: #f59e0b;
}

.empty-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder, #64748b);
  font-style: italic;
}

.guardrail-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
