<template>
  <PageFrame
    title="风控"
    subtitle="规则版本 v0.2 · 敞口与限额 · 告警列表 · 对齐 /trade/risk"
    badge="「风控 /trade/risk」"
    :loading="loading"
  >
    <template #actions>
      <el-tag effect="plain" size="small">规则版本 v0.2 STUB</el-tag>
      <el-button @click="openRule()">规则配置</el-button>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · 由账户 + 持仓聚合 · stubAccount / stubPositions / stubRiskAlerts" type="warning" show-icon :closable="false" />
    <el-alert v-else title="限额由账户与持仓聚合（规则 v0.2 STUB）· 告警优先走 /trade/risk/events" type="info" show-icon :closable="false" />

    <div class="stat-strip risk-stats">
      <article class="stat-tile glass-panel">
        <span>总敞口</span>
        <strong class="numeric">{{ money(metrics.exposure) }}</strong>
        <small>{{ positions.length }} 只持仓</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>单票上限</span>
        <strong class="numeric">{{ pct(metrics.singleCapPct) }}</strong>
        <small>相对净资产 {{ money(metrics.singleCapAbs) }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>日亏限额</span>
        <strong class="numeric">{{ pct(metrics.dailyLossCapPct) }}</strong>
        <small>今日 {{ signedMoney(metrics.todayPnl) }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>杠杆</span>
        <strong class="numeric">{{ metrics.leverageText }}</strong>
        <small>仓位 {{ pct(metrics.positionPct) }}</small>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>敞口限额</h3></template>
      <div class="limit-list">
        <div v-for="bar in bars" :key="bar.key" class="limit-row" :class="{ warn: bar.warn, danger: bar.danger }">
          <div class="limit-meta">
            <strong>{{ bar.label }}</strong>
            <span class="numeric">{{ bar.valueText }} / {{ bar.capText }}</span>
          </div>
          <div class="limit-track"><i :style="{ width: bar.pctText }" /></div>
          <small class="muted">{{ bar.pctText }}{{ bar.hint ? ` · ${bar.hint}` : '' }}</small>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>告警</h3></template>
      <div v-if="alerts.length" class="alert-list">
        <article v-for="item in alerts" :key="item.id" class="alert-item">
          <span class="lvl" :class="`is-${item.level}`">{{ levelLabel(item.level) }}</span>
          <div class="alert-copy">
            <strong>{{ item.title }}</strong>
            <p>{{ item.body }}</p>
          </div>
          <time class="numeric muted">{{ item.time }}</time>
        </article>
      </div>
      <el-empty v-else description="暂无风控告警" :image-size="64" />
    </el-card>

    <el-dialog v-model="dlg" title="规则配置 · v0.2 STUB" width="480px">
      <el-form label-width="88px">
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

    <template #legend>
      <span>tabular-nums · glass-panel · 账户/持仓聚合限额 · GET /trade/account + /trade/positions</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { getTradeAccount, getTradePositions, listRiskEvents, saveRiskRule } from '@/api/trade'
import { unwrap, unwrapList } from '@/utils/list'
import { stubAccount, stubPositions, stubRiskAlerts } from '@/utils/stubs'

const SINGLE_CAP = 0.3
const DAILY_LOSS_CAP = 0.05

const loading = ref(false)
const usingStub = ref(false)
const account = ref({})
const positions = ref([])
const alerts = ref([])
const dlg = ref(false)
const form = ref({})

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : NaN
}
function money(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return v.toLocaleString('en-US', { maximumFractionDigits: 0 })
}
function signedMoney(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return `${v > 0 ? '+' : ''}${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
function pct(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return `${v.toFixed(1)}%`
}
function rowValue(row) {
  const qty = num(row.quantity)
  const px = num(row.last ?? row.currentPrice ?? row.price)
  if (Number.isFinite(qty) && Number.isFinite(px)) return qty * px
  return num(row.marketValue) || 0
}

const metrics = computed(() => {
  const acc = account.value || {}
  const rows = positions.value
  const mvApi = num(acc.marketValue ?? acc.totalMarketValue)
  const exposure = Number.isFinite(mvApi) ? mvApi : rows.reduce((s, r) => s + rowValue(r), 0)
  const net = num(acc.netAssets)
  const today = num(acc.todayPnl ?? acc.dailyPnl)
  const ratio = num(acc.positionRatio)
  const positionPct = Number.isFinite(ratio) ? ratio * (ratio > 1 ? 1 : 100) : (net ? (exposure / net) * 100 : 0)
  const leverage = net ? exposure / net : positionPct / 100
  return {
    exposure,
    net: Number.isFinite(net) ? net : exposure,
    singleCapPct: SINGLE_CAP * 100,
    singleCapAbs: (Number.isFinite(net) ? net : exposure) * SINGLE_CAP,
    dailyLossCapPct: DAILY_LOSS_CAP * 100,
    todayPnl: Number.isFinite(today) ? today : 0,
    positionPct,
    leverageText: Number.isFinite(leverage) ? `${leverage.toFixed(2)}x` : '--'
  }
})

const bars = computed(() => {
  const m = metrics.value
  const rows = [...positions.value].sort((a, b) => rowValue(b) - rowValue(a))
  const top = rows[0]
  const topVal = top ? rowValue(top) : 0
  const topName = top ? `${top.symbol || ''} ${top.symbolName || top.name || ''}`.trim() : '—'
  const singlePct = m.singleCapAbs ? (topVal / m.singleCapAbs) * 100 : 0
  const lossUsed = m.todayPnl < 0 && m.net ? (Math.abs(m.todayPnl) / (m.net * DAILY_LOSS_CAP)) * 100 : 0
  const expoCap = m.net
  const expoPct = expoCap ? (m.exposure / expoCap) * 100 : m.positionPct
  const levPct = Math.min(200, (Number.parseFloat(m.leverageText) || 0) * 50)
  return [
    {
      key: 'expo',
      label: '总敞口 / 净资产',
      valueText: money(m.exposure),
      capText: money(m.net),
      pctText: `${Math.min(100, expoPct).toFixed(1)}%`,
      warn: expoPct >= 80,
      danger: expoPct >= 100,
      hint: expoPct >= 80 ? '接近满仓' : ''
    },
    {
      key: 'single',
      label: `单票集中度 · ${topName}`,
      valueText: money(topVal),
      capText: money(m.singleCapAbs),
      pctText: `${Math.min(140, singlePct).toFixed(1)}%`,
      warn: singlePct >= 80,
      danger: singlePct >= 100,
      hint: singlePct >= 100 ? '已超单票上限' : singlePct >= 80 ? '接近单票上限' : ''
    },
    {
      key: 'loss',
      label: '日亏占用',
      valueText: signedMoney(m.todayPnl),
      capText: `−${money(m.net * DAILY_LOSS_CAP)}`,
      pctText: `${Math.min(100, lossUsed).toFixed(1)}%`,
      warn: lossUsed >= 70,
      danger: lossUsed >= 100,
      hint: m.todayPnl >= 0 ? '当日未触发亏损限额' : ''
    },
    {
      key: 'lev',
      label: '杠杆占用',
      valueText: m.leverageText,
      capText: '2.00x',
      pctText: `${Math.min(100, levPct).toFixed(1)}%`,
      warn: levPct >= 70,
      danger: levPct >= 100,
      hint: ''
    }
  ]
})

function levelLabel(level) {
  return { danger: '严重', warn: '警告', warning: '警告', info: '提示', success: '正常' }[level] || '提示'
}

function mapEvent(row, i) {
  const status = String(row.reviewStatus || '').toLowerCase()
  const level = row.level || (status === 'pending_review' || status === 'overdue' ? 'warn' : status === 'confirmed' ? 'danger' : 'info')
  return {
    id: row.eventId || row.id || `ev-${i}`,
    level,
    title: row.title || row.ruleName || '风控事件',
    body: row.content || row.message || row.handleRemark || row.symbol || '',
    time: String(row.createTime || row.time || '').slice(-8)
  }
}

function applyStub() {
  usingStub.value = true
  account.value = stubAccount()
  positions.value = stubPositions()
  alerts.value = stubRiskAlerts()
}

async function load() {
  loading.value = true
  try {
    alerts.value = []
    const [posRes, accRes, evRes] = await Promise.allSettled([
      getTradePositions(),
      getTradeAccount(),
      listRiskEvents(50)
    ])
    let live = false
    if (posRes.status === 'fulfilled') {
      const d = unwrap(posRes.value)
      const rows = d.positions || unwrapList(posRes.value)
      if (rows.length || d.configured) {
        positions.value = rows
        live = true
      }
    }
    if (accRes.status === 'fulfilled') {
      const acc = unwrap(accRes.value)
      if (acc && (acc.netAssets != null || acc.availableCash != null || acc.currency)) {
        account.value = acc
        live = true
      }
    }
    if (evRes.status === 'fulfilled') {
      const data = unwrap(evRes.value)
      const rows = Array.isArray(data) ? data : unwrapList(evRes.value)
      if (rows.length) alerts.value = rows.map(mapEvent)
    }
    if (!live) applyStub()
    else {
      usingStub.value = false
      if (!alerts.value.length) alerts.value = stubRiskAlerts()
    }
  } catch {
    applyStub()
  } finally {
    loading.value = false
  }
}

function openRule(row) {
  form.value = row ? { ...row } : { ruleName: '单票集中度', ruleType: 'concentration', threshold: 30, enabled: '1' }
  dlg.value = true
}

async function save() {
  try {
    await saveRiskRule(form.value)
    ElMessage.success('已保存')
  } catch {
    ElMessage.success('已保存（STUB）')
  }
  dlg.value = false
}

onMounted(load)
</script>

<style scoped>
.risk-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
h3 { margin: 0; font-size: 15px; }
.limit-list { display: grid; gap: 14px; }
.limit-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.limit-track {
  height: 8px;
  border-radius: 999px;
  background: var(--surface-muted);
  overflow: hidden;
}
.limit-track i {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--accent) 60%, transparent);
}
.limit-row.warn .limit-track i { background: #d97706; }
.limit-row.danger .limit-track i { background: var(--order-buy-solid); }
.muted { color: var(--text-secondary); font-size: 12px; }
.alert-list { display: grid; gap: 10px; }
.alert-item {
  display: grid;
  grid-template-columns: 52px 1fr auto;
  gap: 10px;
  align-items: start;
  padding: 8px 0;
  border-bottom: 1px solid var(--control-border);
}
.alert-item:last-child { border-bottom: 0; }
.alert-copy p { margin: 4px 0 0; color: var(--text-secondary); font-size: 13px; }
.lvl {
  display: inline-flex;
  justify-content: center;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.lvl.is-danger {
  color: var(--order-buy-solid);
  background: color-mix(in srgb, var(--stat-up) var(--chip-fill), transparent);
}
.lvl.is-warn, .lvl.is-warning {
  color: #d97706;
  background: color-mix(in srgb, #f59e0b var(--chip-fill), transparent);
}
.lvl.is-info, .lvl.is-success {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
}
@media (max-width: 900px) { .risk-stats { grid-template-columns: 1fr 1fr; } }
</style>
