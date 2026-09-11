<template>
  <PageFrame
    title="风控"
    subtitle="组合指标 · 规则 · 事件审批 · GET /trade/risk"
    :loading="loading"
  >
    <template #actions>
      <el-tag v-if="usingStub" effect="plain" size="small">演示·stub</el-tag>
      <el-button type="warning" :loading="scanning" @click="scan">执行扫描</el-button>
      <el-button @click="openRule()">新增规则</el-button>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <TradeAuthBanner :visible="brokerAuth" :code="brokerCode" :cached="usingCache" />
    <el-alert v-if="loadError && !usingStub" :title="loadError" type="error" show-icon :closable="false" />

    <el-card shadow="never" class="glass-panel" v-loading="sheetLoading">
      <template #header>
        <div class="card-head">
          <h3>组合收益指标</h3>
          <span class="muted">{{ sheet.message || '持仓加权 · Sharpe / 回撤 / VaR' }}</span>
        </div>
      </template>
      <div v-if="sheetCards.length" class="metric-row">
        <article v-for="card in sheetCards" :key="card.label">
          <span>{{ card.label }}</span>
          <strong class="numeric">{{ card.value }}</strong>
        </article>
      </div>
      <el-empty v-else :description="sheet.message || '暂无持仓或日K不足'" :image-size="56" />
    </el-card>

    <el-card v-if="hasLiveExposure" shadow="never" class="glass-panel">
      <template #header><h3>敞口限额</h3></template>
      <div class="limit-list">
        <div v-for="bar in bars" :key="bar.key" class="limit-row" :class="{ warn: bar.warn, danger: bar.danger, ok: bar.ok }">
          <div class="limit-meta">
            <div>
              <strong>{{ bar.label }}</strong>
              <small class="muted">{{ bar.hint }}</small>
            </div>
            <span class="numeric">{{ bar.valueText }}</span>
          </div>
          <div class="limit-track"><i :style="{ width: bar.width }" /></div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="12">
      <el-col :md="10" :xs="24">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-head">
              <h3>风控规则</h3>
              <span class="muted">{{ rules.length }} 条</span>
            </div>
          </template>
          <el-table :data="rules" stripe empty-text="暂无规则">
            <el-table-column prop="ruleName" label="名称" min-width="120" />
            <el-table-column prop="ruleType" label="类型" width="100" />
            <el-table-column prop="threshold" label="阈值" width="72" align="right">
              <template #default="{ row }"><span class="numeric">{{ row.threshold ?? '—' }}</span></template>
            </el-table-column>
            <el-table-column label="启用" width="72">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled === '1' ? 'success' : 'info'">{{ row.enabled === '1' ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRule(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :md="14" :xs="24">
        <el-card shadow="never" class="glass-panel">
          <template #header>
            <div class="card-head">
              <h3>风险事件</h3>
              <span class="muted">最近 {{ events.length }} 条</span>
            </div>
          </template>
          <div v-if="events.length" class="alert-list">
            <article v-for="item in events" :key="item.eventId || item.id" class="alert-item">
              <span class="lvl" :class="`is-${eventLevel(item)}`">{{ levelLabel(eventLevel(item)) }}</span>
              <div class="alert-copy">
                <strong>{{ item.title }} <time class="numeric muted">{{ item.createTime || item.time || '—' }}</time></strong>
                <p>{{ item.content || item.body || item.handleRemark || '—' }}</p>
                <span class="muted">{{ item.reviewStatusLabel || item.reviewStatus || '' }} {{ item.symbol || '' }}</span>
              </div>
            </article>
          </div>
          <el-empty v-else :description="emptyEvents" :image-size="64" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dlg" title="风控规则" width="480px">
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
      <span>tabular-nums · glass-panel · GET /trade/risk/tearsheet · /rules · /events · POST /evaluate</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import TradeAuthBanner from '@/components/page/TradeAuthBanner.vue'
import { evaluateRisk, getRiskTearsheet, getTradeAccount, getTradePositions, listRiskEvents, listRiskRules, saveRiskRule } from '@/api/trade'
import { useUserStore } from '@/store/user'
import { unwrap, unwrapList } from '@/utils/list'
import { errorText, isDemoSession, stubAccount, stubPositions, stubRiskAlerts } from '@/utils/stubs'
import { brokerAuthCode, cacheTradeAccount, cacheTradePositions, isBrokerAuthError, readCachedAccount, readCachedPositions } from '@/utils/tradeAuth'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const SINGLE_CAP = 0.25
const INDUSTRY_CAP = 0.4
const DAILY_LOSS_CAP = 50000
const OVERNIGHT_CAP = 20
const LOSS_WATCH = -3

const loading = ref(false)
const scanning = ref(false)
const sheetLoading = ref(false)
const usingStub = ref(false)
const brokerAuth = ref(false)
const brokerCode = ref('')
const usingCache = ref(false)
const loadError = ref('')
const account = ref({})
const positions = ref([])
const rules = ref([])
const events = ref([])
const sheet = ref({})
const dlg = ref(false)
const form = ref({})

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : NaN
}
function money(n, ccy) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  const prefix = ccy ? `${ccy} ` : ''
  return `${prefix}${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
function pct(n, d = 1) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return `${v.toFixed(d)}%`
}
function rowValue(row) {
  const qty = num(row.quantity)
  const px = num(row.last ?? row.currentPrice ?? row.price)
  if (Number.isFinite(qty) && Number.isFinite(px)) return qty * px
  return num(row.marketValue) || 0
}
function rowPnlPct(row) {
  const n = num(row.pnlPct ?? row.pnlRate ?? row.unrealizedPnlRate)
  if (Number.isFinite(n)) return n
  const cost = num(row.costPrice)
  const px = num(row.last ?? row.currentPrice ?? row.price)
  if (cost && Number.isFinite(px)) return ((px / cost) - 1) * 100
  return NaN
}
function rowName(row) {
  return row.symbolName || row.name || row.symbol || '--'
}
function inferIndustry(row) {
  if (row.category) return row.category
  const s = String(row.symbol || '').replace(/\.(HK|US|SH|SZ)$/i, '')
  if (['00700', '03690', '09988', '01024', '09618'].includes(s)) return '互联网'
  if (['300750', '002594'].includes(s)) return '新能源'
  return row.industry || '其他'
}

const currency = computed(() => account.value.currency || 'HKD')
const hasLiveExposure = computed(() => !usingStub.value && (positions.value.length > 0 || account.value.netAssets != null || account.value.availableCash != null))

function fmtSheetPct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(2)}%`
}
function fmtSheetNum(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toFixed(2)
}
const sheetCards = computed(() => {
  const s = sheet.value || {}
  if (!s.days && s.sharpe == null && s.maxDrawdown == null && s.totalReturn == null) return []
  return [
    { label: 'Sharpe', value: fmtSheetNum(s.sharpe) },
    { label: 'Sortino', value: fmtSheetNum(s.sortino) },
    { label: '最大回撤', value: fmtSheetPct(s.maxDrawdown) },
    { label: '年化波动', value: fmtSheetPct(s.volatility) },
    { label: 'VaR 95', value: fmtSheetPct(s.var95) },
    { label: '累计收益', value: fmtSheetPct(s.totalReturn) }
  ]
})
const emptyEvents = computed(() => {
  if (loadError.value && !events.value.length) return '风控事件加载失败，请稍后重试'
  return '暂无风控事件（规则探测器未命中），可点击「执行扫描」复检'
})
function eventLevel(item) {
  return item.eventLevel || item.level || 'info'
}

const metrics = computed(() => {
  const acc = account.value || {}
  const rows = positions.value
  const mvApi = num(acc.marketValue ?? acc.totalMarketValue)
  const exposure = Number.isFinite(mvApi) ? mvApi : rows.reduce((s, r) => s + rowValue(r), 0)
  const net = num(acc.netAssets)
  const cash = num(acc.availableCash)
  const today = num(acc.todayPnl ?? acc.dailyPnl)
  const ratio = num(acc.positionRatio)
  const positionPct = Number.isFinite(ratio) ? (ratio > 1 ? ratio : ratio * 100) : (net ? (exposure / net) * 100 : 0)
  const ranked = [...rows].sort((a, b) => rowValue(b) - rowValue(a))
  const top = ranked[0]
  const topVal = top ? rowValue(top) : 0
  const topShare = exposure ? (topVal / exposure) * 100 : 0
  const industryMap = new Map()
  for (const row of rows) {
    const key = `${String(row.market || '').toUpperCase() === 'HK' ? '港股' : ''}${inferIndustry(row)}`
    industryMap.set(key, (industryMap.get(key) || 0) + rowValue(row))
  }
  const industry = [...industryMap.entries()].sort((a, b) => b[1] - a[1])[0] || ['—', 0]
  const industryPct = exposure ? (industry[1] / exposure) * 100 : 0
  const lossUsed = Number.isFinite(today) ? Math.abs(today) : 0
  const lossUsedPct = DAILY_LOSS_CAP ? (lossUsed / DAILY_LOSS_CAP) * 100 : 0
  const overnight = rows.length
  const worst = ranked.find((r) => rowPnlPct(r) <= LOSS_WATCH)
  return {
    exposure,
    net: Number.isFinite(net) ? net : exposure,
    cash: Number.isFinite(cash) ? cash : 0,
    todayPnl: Number.isFinite(today) ? today : 0,
    positionPct,
    top,
    topShare,
    industryLabel: industry[0],
    industryPct,
    lossUsed,
    lossUsedPct,
    overnight,
    worst,
    leverage: num(acc.leverage) || 1,
    financing: Boolean(acc.financingEnabled || acc.marginEnabled)
  }
})

function barWidth(usedPct) {
  return `${Math.max(0, Math.min(100, usedPct))}%`
}

const bars = computed(() => {
  const m = metrics.value
  const top = m.top
  const singleUsed = SINGLE_CAP ? (m.topShare / (SINGLE_CAP * 100)) * 100 : 0
  const industryUsed = INDUSTRY_CAP ? (m.industryPct / (INDUSTRY_CAP * 100)) * 100 : 0
  const overnightUsed = (m.overnight / OVERNIGHT_CAP) * 100
  const cashHealthy = m.cash > 0
  return [
    {
      key: 'single',
      label: `单票市值占比 ${pct(m.topShare)} / ${pct(SINGLE_CAP * 100, 0)}`,
      valueText: `${pct(m.topShare)} / ${pct(SINGLE_CAP * 100, 0)}`,
      hint: top ? `${rowName(top)} ${String(top.symbol || '').replace(/\.(HK|US|SH|SZ)$/i, '')}` : '暂无持仓',
      width: barWidth(singleUsed),
      warn: singleUsed >= 80,
      danger: singleUsed >= 100
    },
    {
      key: 'industry',
      label: `行业集中度 · ${m.industryLabel || '互联网'} ${pct(m.industryPct, 0)} / ${pct(INDUSTRY_CAP * 100, 0)}`,
      valueText: `${pct(m.industryPct, 0)} / ${pct(INDUSTRY_CAP * 100, 0)}`,
      hint: `${m.industryLabel || '行业'}合计`,
      width: barWidth(industryUsed),
      warn: industryUsed >= 80,
      danger: industryUsed >= 100
    },
    {
      key: 'loss',
      label: `日亏损占用 ${money(m.lossUsed, currency.value)} / ${money(DAILY_LOSS_CAP, currency.value)}`,
      valueText: `${money(m.lossUsed, currency.value)} / ${money(DAILY_LOSS_CAP, currency.value)}`,
      hint: '今日浮动盈亏占用',
      width: barWidth(m.lossUsedPct),
      warn: m.lossUsedPct >= 70,
      danger: m.lossUsedPct >= 100
    },
    {
      key: 'cash',
      label: `可用保证金缓冲 ${money(m.cash, currency.value)}`,
      valueText: money(m.cash, currency.value),
      hint: cashHealthy ? '现金可用充足' : '现金紧张',
      width: barWidth(cashHealthy ? 28 : 85),
      ok: cashHealthy,
      warn: !cashHealthy,
      danger: false
    },
    {
      key: 'overnight',
      label: `隔夜持仓上限 ${m.overnight} / ${OVERNIGHT_CAP} 只`,
      valueText: `${m.overnight} / ${OVERNIGHT_CAP} 只`,
      hint: '跨市场合计',
      width: barWidth(overnightUsed),
      warn: overnightUsed >= 70,
      danger: overnightUsed >= 100
    }
  ]
})

function levelLabel(level) {
  return { danger: '严重', warn: '预警', warning: '预警', info: '信息', ok: '正常', success: '正常' }[level] || '信息'
}

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  usingCache.value = false
  loadError.value = ''
  account.value = stubAccount()
  positions.value = stubPositions()
  events.value = stubRiskAlerts().map((a, i) => ({
    eventId: a.id || i,
    title: a.title,
    content: a.body,
    eventLevel: a.level,
    createTime: a.time
  }))
  rules.value = [
    { ruleId: 'stub-1', ruleName: '单票集中度', ruleType: 'concentration', threshold: 25, enabled: '1' }
  ]
  sheet.value = { sharpe: 1.12, sortino: 1.34, maxDrawdown: -0.08, volatility: 0.16, var95: -0.021, totalReturn: 0.094, days: 120 }
}

async function loadSheet() {
  sheetLoading.value = true
  try {
    const res = await getRiskTearsheet({ days: 120 })
    sheet.value = unwrap(res) || {}
  } catch (e) {
    sheet.value = { message: isBrokerAuthError(e) ? '长桥凭证不可用，组合指标暂不可用' : errorText(e, '组合指标暂不可用') }
    if (isBrokerAuthError(e)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(e)
    }
  } finally {
    sheetLoading.value = false
  }
}

async function loadExposure() {
  try {
    const [posRes, accRes] = await Promise.allSettled([getTradePositions(), getTradeAccount()])
    const brokerErr = [posRes, accRes].find((r) => r.status === 'rejected' && isBrokerAuthError(r.reason))
    if (brokerErr) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(brokerErr.reason)
      const cachedRows = readCachedPositions()
      const cachedAcc = readCachedAccount()
      if (cachedRows.length) positions.value = cachedRows
      if (cachedAcc) account.value = cachedAcc
      usingCache.value = Boolean(cachedRows.length || cachedAcc)
      if (!cachedRows.length) positions.value = []
      if (!cachedAcc) account.value = {}
      return
    }
    if (posRes.status === 'fulfilled') {
      const d = unwrap(posRes.value)
      const rows = d.positions || unwrapList(posRes.value)
      positions.value = rows
      cacheTradePositions(rows)
    } else positions.value = []
    if (accRes.status === 'fulfilled') {
      const acc = unwrap(accRes.value)
      account.value = acc && typeof acc === 'object' ? acc : {}
      if (account.value.netAssets != null || account.value.availableCash != null) cacheTradeAccount(account.value)
    } else account.value = {}
  } catch (e) {
    if (isBrokerAuthError(e)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(e)
    }
    positions.value = []
    account.value = {}
  }
}

async function load() {
  if (demoMode()) {
    applyStub()
    return
  }
  loading.value = true
  brokerAuth.value = false
  usingCache.value = false
  usingStub.value = false
  loadError.value = ''
  const errors = []
  loadSheet()
  loadExposure()
  try {
    const [ruleRes, eventRes] = await Promise.allSettled([listRiskRules(), listRiskEvents(200)])
    if (ruleRes.status === 'fulfilled') rules.value = unwrapList(ruleRes.value)
    else {
      rules.value = []
      errors.push(errorText(ruleRes.reason, '规则加载失败'))
    }
    if (eventRes.status === 'fulfilled') events.value = unwrapList(eventRes.value)
    else {
      events.value = []
      if (isBrokerAuthError(eventRes.reason)) {
        brokerAuth.value = true
        brokerCode.value = brokerAuthCode(eventRes.reason)
      } else errors.push(errorText(eventRes.reason, '事件加载失败'))
    }
    if (errors.length) loadError.value = errors.join('；')
  } catch (e) {
    rules.value = []
    events.value = []
    loadError.value = errorText(e, '风控加载失败')
  } finally {
    loading.value = false
  }
}

async function scan() {
  if (demoMode()) {
    ElMessage.success('已扫描（演示·stub）')
    return
  }
  scanning.value = true
  try {
    const res = await evaluateRisk()
    ElMessage.success(res.msg || unwrap(res).message || '扫描完成')
    await load()
  } catch (e) {
    if (isBrokerAuthError(e)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(e)
    }
    ElMessage.error(errorText(e, '扫描失败'))
  } finally {
    scanning.value = false
  }
}

function openRule(row) {
  form.value = row
    ? { ...row }
    : { ruleName: '', ruleType: 'concentration', threshold: 25, enabled: '1' }
  dlg.value = true
}

async function save() {
  if (demoMode()) {
    ElMessage.success('已保存（演示·stub）')
    dlg.value = false
    return
  }
  try {
    await saveRiskRule(form.value)
    ElMessage.success('已保存')
    dlg.value = false
    load()
  } catch (e) {
    ElMessage.error(errorText(e, '保存失败'))
  }
}

onMounted(load)
</script>

<style scoped>
.metric-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.metric-row article { display: grid; gap: 4px; }
.metric-row span { color: var(--text-secondary); font-size: 12px; }
.metric-row strong { font-size: 22px; color: var(--text-emphasis); }
.metric-row small { color: var(--text-secondary); font-size: 12px; }
h3 { margin: 0; font-size: 15px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.limit-list { display: grid; gap: 16px; }
.limit-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 6px; align-items: flex-start; }
.limit-meta div { display: grid; gap: 2px; }
.limit-track {
  height: 6px;
  border-radius: 999px;
  background: var(--surface-muted, color-mix(in srgb, var(--text-secondary) 16%, transparent));
  overflow: hidden;
}
.limit-track i {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--accent) 60%, transparent);
}
.limit-row.warn .limit-track i { background: #d97706; }
.limit-row.danger .limit-track i { background: var(--order-buy-solid); }
.limit-row.ok .limit-track i { background: var(--order-sell-solid); }
.muted { color: var(--text-secondary); font-size: 12px; }
.alert-list { display: grid; gap: 12px; }
.alert-item {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 10px;
  align-items: start;
  padding: 6px 0;
  border-bottom: 1px solid var(--control-border);
}
.alert-item:last-child { border-bottom: 0; }
.alert-copy p { margin: 4px 0 0; color: var(--text-secondary); font-size: 13px; }
.alert-copy time { margin-left: 8px; font-weight: 500; }
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
.lvl.is-info {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
}
.lvl.is-ok, .lvl.is-success {
  color: var(--order-sell-solid);
  background: color-mix(in srgb, var(--stat-down) var(--chip-fill), transparent);
}
@media (max-width: 900px) { .metric-row { grid-template-columns: 1fr 1fr; } }
.el-col { margin-bottom: 12px; }
</style>
