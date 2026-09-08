<template>
  <PageFrame title="风控" :loading="loading">
    <template #actions>
      <el-button type="warning" :loading="scanning" @click="scan">执行扫描</el-button>
      <el-button type="primary" @click="openRule()">新增规则</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article v-for="card in sheetCards" :key="card.label" class="stat-tile glass-panel">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </article>
    </div>

    <div class="stat-strip">
      <article v-for="card in statusCards" :key="card.key" class="stat-tile glass-panel" :class="{ active: filter === card.key }" @click="filter = card.key">
        <span>{{ card.label }}</span>
        <strong>{{ card.count }}</strong>
      </article>
    </div>

    <el-row :gutter="12">
      <el-col :md="10" :xs="24">
        <el-card shadow="never" class="glass-panel">
          <template #header><div class="card-header"><h3>风控规则</h3></div></template>
          <el-table :data="rules" size="small" empty-text="暂无规则">
            <el-table-column prop="ruleName" label="名称" min-width="120" />
            <el-table-column prop="ruleType" label="类型" width="110" />
            <el-table-column prop="threshold" label="阈值" width="80" />
            <el-table-column prop="enabled" label="启用" width="70">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled === '1' ? 'success' : 'info'">{{ row.enabled === '1' ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column width="140">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRule(row)">编辑</el-button>
                <el-button link type="danger" @click="remove(row)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :md="14" :xs="24">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-header">
              <h3>风险事件</h3>
              <el-radio-group v-model="filter" size="small">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="pending_review">待复核</el-radio-button>
                <el-radio-button value="confirmed">已确认</el-radio-button>
                <el-radio-button value="ignored">已忽略</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="filteredEvents" size="small" max-height="480" empty-text="暂无风控事件">
            <el-table-column prop="createTime" label="时间" width="160" />
            <el-table-column label="状态" width="92">
              <template #default="{ row }">
                <el-tag size="small" :type="statusTone(row.reviewStatus)">{{ row.reviewStatusLabel || '待复核' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="symbol" label="标的" width="90" />
            <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
            <el-table-column width="140">
              <template #default="{ row }">
                <el-button v-if="canAct(row, 'confirmed')" link type="success" @click="openAction(row, 'confirmed')">确认</el-button>
                <el-button v-if="canAct(row, 'ignored')" link @click="openAction(row, 'ignored')">忽略</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dlg" title="风控规则" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.ruleName" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.ruleType" style="width: 100%">
            <el-option label="仓位" value="position" />
            <el-option label="亏损" value="loss" />
            <el-option label="集中度" value="concentration" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值"><el-input-number v-model="form.threshold" :min="0" :max="100" style="width: 100%" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" active-value="1" inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="actionDlg" :title="actionTitle" width="460px">
      <el-form label-width="80px">
        <el-form-item label="事件">{{ actionRow.title }}</el-form-item>
        <el-form-item label="处理备注">
          <el-input v-model="actionRemark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDlg = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitAction">提交</el-button>
      </template>
    </el-dialog>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { deleteRiskRule, evaluateRisk, getRiskTearsheet, listRiskEvents, listRiskRules, saveRiskRule, updateRiskEventStatus } from '@/api/trade'
import { unwrap, unwrapList } from '@/utils/list'

const ALLOWED = {
  pending_review: ['confirmed', 'ignored'],
  need_review: ['confirmed', 'ignored'],
  overdue: ['confirmed', 'ignored'],
  confirmed: [],
  ignored: []
}

const loading = ref(false)
const scanning = ref(false)
const acting = ref(false)
const rules = ref([])
const events = ref([])
const sheet = ref({})
const filter = ref('all')
const dlg = ref(false)
const form = ref({})
const actionDlg = ref(false)
const actionRow = ref({})
const actionStatus = ref('')
const actionRemark = ref('')

function fmtPct(v) {
  const n = Number(v)
  return Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '--'
}
function fmtNum(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}

const sheetCards = computed(() => [
  { label: 'Sharpe', value: fmtNum(sheet.value.sharpe) },
  { label: '最大回撤', value: fmtPct(sheet.value.maxDrawdown) },
  { label: '年化波动', value: fmtPct(sheet.value.volatility) },
  { label: '累计收益', value: fmtPct(sheet.value.totalReturn) }
])
const countBy = (status) => events.value.filter((e) => (e.reviewStatus || 'pending_review') === status).length
const statusCards = computed(() => [
  { key: 'all', label: '全部', count: events.value.length },
  { key: 'pending_review', label: '待复核', count: countBy('pending_review') },
  { key: 'confirmed', label: '已确认', count: countBy('confirmed') },
  { key: 'ignored', label: '已忽略', count: countBy('ignored') }
])
const filteredEvents = computed(() => (filter.value === 'all' ? events.value : events.value.filter((e) => (e.reviewStatus || 'pending_review') === filter.value)))
const actionTitle = computed(() => (actionStatus.value === 'confirmed' ? '确认事件' : '忽略事件'))

function statusTone(status) {
  return { pending_review: 'warning', confirmed: 'success', ignored: 'info', overdue: 'danger' }[status] || 'warning'
}
function canAct(row, dest) {
  return (ALLOWED[row.reviewStatus || 'pending_review'] || []).includes(dest)
}

async function load() {
  loading.value = true
  try {
    const [s, r, e] = await Promise.allSettled([getRiskTearsheet({ days: 120 }), listRiskRules(), listRiskEvents(200)])
    if (s.status === 'fulfilled') sheet.value = unwrap(s.value)
    if (r.status === 'fulfilled') {
      const data = unwrap(r.value)
      rules.value = Array.isArray(data) ? data : unwrapList(r.value)
    }
    if (e.status === 'fulfilled') {
      const data = unwrap(e.value)
      events.value = Array.isArray(data) ? data : unwrapList(e.value)
    }
  } catch {
    events.value = []
  } finally {
    loading.value = false
  }
}

function openRule(row) {
  form.value = row ? { ...row } : { ruleName: '', ruleType: 'position', threshold: 20, enabled: '1' }
  dlg.value = true
}

async function save() {
  await saveRiskRule(form.value)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}

async function remove(row) {
  await ElMessageBox.confirm('删除规则？', '风控')
  await deleteRiskRule(row.ruleId)
  load()
}

async function scan() {
  scanning.value = true
  try {
    const res = await evaluateRisk()
    ElMessage.success(res.msg || '完成')
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
    ElMessage.error('请填写处理备注')
    return
  }
  acting.value = true
  try {
    await updateRiskEventStatus(actionRow.value.eventId, { reviewStatus: actionStatus.value, handleRemark: actionRemark.value })
    ElMessage.success('状态已更新')
    actionDlg.value = false
    await load()
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.card-header h3 { margin: 0; font-size: 15px; }
.stat-tile.active { border-color: color-mix(in srgb, var(--accent) 40%, var(--border-soft)); cursor: pointer; }
.stat-tile { cursor: pointer; }
</style>
