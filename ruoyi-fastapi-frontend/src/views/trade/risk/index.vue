<template>
  <div class="app-container risk-page">
    <div class="page-hero">
      <div>
        <h2>风控管理</h2>
        <p>规则配置 · 扫描 · 事件审批（待复核 / 已确认 / 已忽略 / 需复核 / 超期）</p>
      </div>
      <div class="acts">
        <el-button type="warning" :loading="scanning" @click="scan" v-hasPermi="['trade:risk:edit']">执行扫描</el-button>
        <el-button type="primary" @click="openRule()" v-hasPermi="['trade:risk:edit']">新增规则</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="metric-row">
      <el-col :xs="12" :sm="8" :md="4" v-for="card in statusCards" :key="card.key">
        <div class="metric-card" :class="{ active: filter === card.key }" @click="filter = card.key">
          <div class="metric-label">{{ card.label }}</div>
          <div class="metric-val" :class="card.tone">{{ card.count }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :md="10" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>风控规则</template>
          <el-table :data="rules" v-loading="loading" size="small">
            <el-table-column prop="ruleName" label="名称" min-width="120"/>
            <el-table-column prop="ruleType" label="类型" width="110"/>
            <el-table-column prop="threshold" label="阈值" width="80"/>
            <el-table-column prop="enabled" label="启用" width="70">
              <template #default="{row}">
                <el-tag size="small" :type="row.enabled==='1'?'success':'info'">{{ row.enabled==='1'?'是':'否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{row}">
                <el-button link type="primary" @click="openRule(row)" v-hasPermi="['trade:risk:edit']">编辑</el-button>
                <el-button link type="danger" @click="remove(row)" v-hasPermi="['trade:risk:edit']">删</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :md="14" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>
            <div class="hdr">
              <span>风险事件</span>
              <el-radio-group v-model="filter" size="small">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="pending_review">待复核</el-radio-button>
                <el-radio-button label="overdue">超期</el-radio-button>
                <el-radio-button label="need_review">需复核</el-radio-button>
                <el-radio-button label="confirmed">已确认</el-radio-button>
                <el-radio-button label="ignored">已忽略</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="filteredEvents" v-loading="loading" size="small" max-height="480">
            <el-table-column prop="createTime" label="时间" width="160"/>
            <el-table-column prop="reviewStatusLabel" label="状态" width="92">
              <template #default="{row}">
                <el-tag size="small" :type="statusTone(row.reviewStatus)">{{ row.reviewStatusLabel || '待复核' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="eventLevel" label="级别" width="72">
              <template #default="{row}">
                <el-tag size="small" :type="row.eventLevel==='danger'?'danger':'warning'">{{ row.eventLevel||'warn' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="symbol" label="标的" width="90">
              <template #default="{row}">
                <el-button v-if="row.symbol" link type="primary" @click="openSymbol(row.symbol)">{{ row.symbol }}</el-button>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip/>
            <el-table-column prop="handleRemark" label="处理备注" min-width="140" show-overflow-tooltip/>
            <el-table-column label="操作" width="210" fixed="right">
              <template #default="{row}">
                <el-button
                  v-if="canAct(row, 'confirmed')"
                  link
                  type="success"
                  @click="openAction(row, 'confirmed')"
                  v-hasPermi="['trade:risk:edit']"
                >确认</el-button>
                <el-button
                  v-if="canAct(row, 'ignored')"
                  link
                  @click="openAction(row, 'ignored')"
                  v-hasPermi="['trade:risk:edit']"
                >忽略</el-button>
                <el-button
                  v-if="canAct(row, 'need_review')"
                  link
                  type="warning"
                  @click="openAction(row, 'need_review')"
                  v-hasPermi="['trade:risk:edit']"
                >需复核</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :description="emptyDescription" :image-size="56"/>
            </template>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dlg" title="风控规则" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.ruleName"/></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.ruleType" style="width:100%">
            <el-option label="仓位 position" value="position"/>
            <el-option label="亏损 loss" value="loss"/>
            <el-option label="集中度 concentration" value="concentration"/>
          </el-select>
        </el-form-item>
        <el-form-item label="阈值"><el-input-number v-model="form.threshold" :min="0" :max="100" style="width:100%"/></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" active-value="1" inactive-value="0"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="actionDlg" :title="actionTitle" width="460px">
      <el-form label-width="80px">
        <el-form-item label="事件">
          <div class="action-title">{{ actionRow.title }}</div>
          <div class="muted">{{ actionRow.symbol || '--' }} · {{ actionRow.createTime }}</div>
        </el-form-item>
        <el-form-item label="处理备注">
          <el-input v-model="actionRemark" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="说明确认/忽略/复核原因"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDlg=false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitAction">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TradeRisk">
import { listRiskRules, saveRiskRule, deleteRiskRule, listRiskEvents, evaluateRisk, updateRiskEventStatus } from '@/api/trade'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const scanning = ref(false)
const acting = ref(false)
const rules = ref([])
const events = ref([])
const dlg = ref(false)
const form = ref({})
const filter = ref('all')
const actionDlg = ref(false)
const actionRow = ref({})
const actionStatus = ref('')
const actionRemark = ref('')
const loadError = ref(false)

const ALLOWED = {
  pending_review: ['confirmed', 'ignored', 'need_review'],
  need_review: ['confirmed', 'ignored'],
  overdue: ['confirmed', 'ignored', 'need_review'],
  confirmed: ['need_review'],
  ignored: ['need_review']
}

const ACTION_LABEL = {
  confirmed: '确认事件',
  ignored: '忽略事件',
  need_review: '标记需复核'
}

const countBy = (status) => events.value.filter((e) => (e.reviewStatus || 'pending_review') === status).length

const statusCards = computed(() => [
  { key: 'all', label: '全部', count: events.value.length, tone: '' },
  { key: 'pending_review', label: '待复核', count: countBy('pending_review'), tone: 'warn' },
  { key: 'overdue', label: '超期', count: countBy('overdue'), tone: 'danger' },
  { key: 'need_review', label: '需复核', count: countBy('need_review'), tone: 'primary' },
  { key: 'confirmed', label: '已确认', count: countBy('confirmed'), tone: 'ok' },
  { key: 'ignored', label: '已忽略', count: countBy('ignored'), tone: '' }
])

const filteredEvents = computed(() => {
  if (filter.value === 'all') return events.value
  return events.value.filter((e) => (e.reviewStatus || 'pending_review') === filter.value)
})

const actionTitle = computed(() => ACTION_LABEL[actionStatus.value] || '处理事件')

const emptyDescription = computed(() => {
  if (loadError.value) return '风控事件加载失败，请稍后重试'
  if (filter.value === 'all' && events.value.length === 0) {
    return '暂无风控事件（规则探测器未命中），可点击右上角「执行扫描」复检'
  }
  return '暂无该状态的风控事件'
})

function statusTone(status) {
  return {
    pending_review: 'warning',
    confirmed: 'success',
    ignored: 'info',
    need_review: '',
    overdue: 'danger'
  }[status] || 'warning'
}

function canAct(row, dest) {
  const src = row.reviewStatus || 'pending_review'
  return (ALLOWED[src] || []).includes(dest)
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const [r, e] = await Promise.all([listRiskRules(), listRiskEvents(200)])
    rules.value = r.data || []
    events.value = e.data || []
  } catch {
    loadError.value = true
    events.value = []
  } finally {
    loading.value = false
  }
}

function openRule(row) {
  form.value = row ? { ...row } : { ruleName: '', ruleType: 'position', threshold: 20, enabled: '1', remark: '' }
  dlg.value = true
}

async function save() {
  await saveRiskRule(form.value)
  proxy.$modal.msgSuccess('已保存')
  dlg.value = false
  load()
}

async function remove(row) {
  await proxy.$modal.confirm('删除规则？')
  await deleteRiskRule(row.ruleId)
  load()
}

async function scan() {
  scanning.value = true
  try {
    const res = await evaluateRisk()
    proxy.$modal.msgSuccess(res.msg || '完成')
    filter.value = 'pending_review'
    await load()
  } finally {
    scanning.value = false
  }
}

function openAction(row, status) {
  actionRow.value = row
  actionStatus.value = status
  actionRemark.value = ''
  actionDlg.value = true
}

async function submitAction() {
  if (!String(actionRemark.value || '').trim()) {
    proxy.$modal.msgError('请填写处理备注')
    return
  }
  acting.value = true
  try {
    await updateRiskEventStatus(actionRow.value.eventId, {
      reviewStatus: actionStatus.value,
      handleRemark: actionRemark.value
    })
    proxy.$modal.msgSuccess('状态已更新')
    actionDlg.value = false
    await load()
  } finally {
    acting.value = false
  }
}

function openSymbol(symbol) {
  proxy.$router.push({ path: '/trade/trading', query: { symbol } })
}

onMounted(load)
</script>

<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)}
.page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.acts{display:flex;gap:8px;flex-wrap:wrap}
.metric-row{margin-bottom:12px}
.metric-card{background:var(--el-bg-color);border:1px solid var(--el-border-color-lighter);border-radius:8px;padding:12px 14px;cursor:pointer;margin-bottom:12px}
.metric-card.active{border-color:var(--el-color-primary)}
.metric-label{font-size:12px;color:var(--text-muted)}
.metric-val{margin-top:4px;font-size:22px;font-weight:600;color:var(--text-emphasis)}
.metric-val.warn{color:var(--el-color-warning)}
.metric-val.danger{color:var(--el-color-danger)}
.metric-val.ok{color:var(--el-color-success)}
.metric-val.primary{color:var(--el-color-primary)}
.hdr{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.mb12{margin-bottom:12px}
.action-title{font-weight:600;color:var(--text-emphasis)}
.muted{color:var(--text-muted);font-size:12px;margin-top:4px}
</style>
