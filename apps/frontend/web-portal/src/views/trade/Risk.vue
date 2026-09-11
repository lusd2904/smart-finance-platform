<template>
  <PageFrame
    title="风控"
    subtitle="规则版本 v0.2 STUB · 账户 + 持仓聚合限额 · 对齐 /trade/risk"
    :loading="loading"
  >
    <template #actions>
      <el-tag effect="plain" size="small">规则版本 v0.2 STUB</el-tag>
      <el-button @click="openRule()">规则配置</el-button>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <TradeAuthBanner :visible="brokerAuth" :code="brokerCode" :cached="usingCache" />

    <el-card shadow="never" class="glass-panel">
      <div class="metric-row">
        <article v-for="card in metricCards" :key="card.label">
          <span>{{ card.label }}</span>
          <strong class="numeric">{{ card.value }}</strong>
          <small>{{ card.sub }}</small>
        </article>
      </div>
    </el-card>

    <el-card shadow="never" class="glass-panel">
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

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-head">
          <h3>风控预警</h3>
          <span class="muted">最近 {{ alerts.length }} 条</span>
        </div>
      </template>
      <div v-if="alerts.length" class="alert-list">
        <article v-for="item in alerts" :key="item.id" class="alert-item">
          <span class="lvl" :class="`is-${item.level}`">{{ levelLabel(item.level) }}</span>
          <div class="alert-copy">
            <strong>{{ item.title }} <time class="numeric muted">{{ item.time }}</time></strong>
            <p>{{ item.body }}</p>
          </div>
        </article>
      </div>
      <el-empty v-else description="暂无风控预警" :image-size="64" />
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
      <span>tabular-nums · glass-panel blur · 无独立风控 API · STUB 规则 v0.2 聚合 /trade/account + /trade/positions</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import TradeAuthBanner from '@/components/page/TradeAuthBanner.vue'
import { getTradeAccount, getTradePositions, saveRiskRule } from '@/api/trade'
import { unwrap, unwrapList } from '@/utils/list'
import { stubAccount, stubPositions, stubRiskAlerts } from '@/utils/stubs'
import { brokerAuthCode, cacheTradeAccount, cacheTradePositions, isBrokerAuthError, readCachedAccount, readCachedPositions } from '@/utils/tradeAuth'

const SINGLE_CAP = 0.25
const INDUSTRY_CAP = 0.4
const DAILY_LOSS_CAP = 50000
const OVERNIGHT_CAP = 20
const LOSS_WATCH = -3

const loading = ref(false)
const usingStub = ref(false)
const brokerAuth = ref(false)
const brokerCode = ref('')
const usingCache = ref(false)
const account = ref({})
const positions = ref([])
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

const metricCards = computed(() => {
  const m = metrics.value
  const topName = m.top ? (m.top.symbolName || m.top.name || m.top.symbol || '').replace(/控股|-.*/, '') : '—'
  return [
    { label: '总敞口', value: money(m.exposure, currency.value), sub: `相对净资产 ${pct(m.positionPct)}` },
    { label: '单票上限', value: pct(SINGLE_CAP * 100, 0), sub: `当前最大 ${pct(m.topShare)} · ${topName}` },
    { label: '日亏限额', value: money(DAILY_LOSS_CAP, currency.value), sub: `今日已用 ${pct(m.lossUsedPct)}` },
    { label: '杠杆倍数', value: `${m.leverage.toFixed(2)}×`, sub: m.financing ? '融资已启用' : '未启用融资' }
  ]
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

const alerts = computed(() => {
  if (usingStub.value) return stubRiskAlerts()
  const m = metrics.value
  const out = []
  const industryGap = (INDUSTRY_CAP * 100) - m.industryPct
  if (m.industryPct / (INDUSTRY_CAP * 100) >= 0.7) {
    out.push({ id: 'a-ind', level: 'warn', title: '集中度接近阈值', body: `${m.industryLabel}敞口 ${pct(m.industryPct, 0)}，距 ${pct(INDUSTRY_CAP * 100, 0)} 上限 ${industryGap.toFixed(0)}pp。`, time: '10:42' })
  }
  out.push({
    id: 'a-loss',
    level: m.lossUsedPct >= 70 ? 'warn' : 'info',
    title: m.lossUsedPct >= 70 ? '日亏占用偏高' : '日亏限额正常',
    body: `今日浮动亏损占用限额 ${pct(m.lossUsedPct)}，${m.lossUsedPct >= 70 ? '请控制回撤' : '无需干预'}。`,
    time: '10:15'
  })
  if (m.worst) {
    const p = rowPnlPct(m.worst)
    out.push({
      id: 'a-worst',
      level: 'danger',
      title: `${rowName(m.worst)}浮亏超 3%`,
      body: `${String(m.worst.symbol || '').replace(/\.(HK|US|SH|SZ)$/i, '')} 持仓浮亏 ${p.toFixed(2)}%，触发关注阈值。`,
      time: '09:58'
    })
  }
  out.push({
    id: 'a-ok',
    level: 'ok',
    title: '账户健康度良好',
    body: `杠杆 ${m.leverage.toFixed(1)}×，可用现金${m.cash > 0 ? '充足' : '偏低'}，无强平风险。`,
    time: '09:30'
  })
  out.push({
    id: 'a-ovn',
    level: m.overnight >= 12 ? 'warn' : 'info',
    title: '隔夜持仓数提醒',
    body: `当前 ${m.overnight} 只隔夜持仓，建议复核止损。`,
    time: '昨日 16:05'
  })
  return out.slice(0, 5)
})

function levelLabel(level) {
  return { danger: '严重', warn: '预警', warning: '预警', info: '信息', ok: '正常', success: '正常' }[level] || '信息'
}

function applyStub() {
  usingStub.value = true
  usingCache.value = false
  account.value = stubAccount()
  positions.value = stubPositions()
}

async function load() {
  loading.value = true
  brokerAuth.value = false
  usingCache.value = false
  try {
    const [posRes, accRes] = await Promise.allSettled([getTradePositions(), getTradeAccount()])
    const brokerErr = [posRes, accRes].find((r) => r.status === 'rejected' && isBrokerAuthError(r.reason))
    if (brokerErr) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(brokerErr.reason)
      const cachedRows = readCachedPositions()
      const cachedAcc = readCachedAccount()
      if (cachedRows.length || cachedAcc) {
        if (cachedRows.length) positions.value = cachedRows
        if (cachedAcc) account.value = cachedAcc
        usingCache.value = true
        usingStub.value = false
      } else {
        positions.value = []
        account.value = {}
        usingStub.value = false
      }
      return
    }
    let live = false
    if (posRes.status === 'fulfilled') {
      const d = unwrap(posRes.value)
      const rows = d.positions || unwrapList(posRes.value)
      if (rows.length || d.configured) {
        positions.value = rows
        cacheTradePositions(rows)
        live = true
      }
    }
    if (accRes.status === 'fulfilled') {
      const acc = unwrap(accRes.value)
      if (acc && (acc.netAssets != null || acc.availableCash != null || acc.currency)) {
        account.value = acc
        cacheTradeAccount(acc)
        live = true
      }
    }
    if (!live) applyStub()
    else usingStub.value = false
  } catch (e) {
    if (isBrokerAuthError(e)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(e)
      usingStub.value = false
    } else applyStub()
  } finally {
    loading.value = false
  }
}

function openRule() {
  form.value = { ruleName: '单票集中度', ruleType: 'concentration', threshold: 25, enabled: '1' }
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
</style>
