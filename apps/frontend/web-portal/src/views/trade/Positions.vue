<template>
  <PageFrame
    title="持仓"
    subtitle="账户汇总 · 实时持仓表 · 涨红跌绿 · 对齐 Terminal /trade API"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="market">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" clearable placeholder="代码 / 名称" style="width:160px" />
      <el-select v-if="accounts.length > 1" v-model="accountId" style="width:160px">
        <el-option v-for="a in accounts" :key="a.id" :label="a.label" :value="a.id" />
      </el-select>
      <el-tag v-else effect="plain" size="small">账户 {{ account.currency || 'HKD' }} 主账户</el-tag>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <TradeAuthBanner :visible="brokerAuth" :code="brokerCode" :cached="usingCache" />
    <el-alert v-if="usingStub && !brokerAuth" title="STUB · stubAccount / stubPositions" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="msg && !brokerAuth" :title="msg" type="info" show-icon :closable="false" />

    <div class="stat-strip pos-stats">
      <article class="stat-tile glass-panel">
        <span>总市值</span>
        <strong class="numeric">{{ money(summary.marketValue) }}</strong>
        <small>{{ list.length }} 只持仓 · 多市场</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>今日盈亏</span>
        <strong class="numeric" :class="changeClass(summary.todayPnl)">{{ signedMoney(summary.todayPnl) }}</strong>
        <small :class="changeClass(summary.todayPnlPct)">{{ fmtChange(summary.todayPnlPct) }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>持仓盈亏</span>
        <strong class="numeric" :class="changeClass(summary.unrealized)">{{ signedMoney(summary.unrealized) }}</strong>
        <small :class="changeClass(summary.unrealizedPct)">{{ fmtChange(summary.unrealizedPct) }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>可用资金</span>
        <strong class="numeric">{{ money(account.availableCash) }}</strong>
        <small>currency {{ account.currency || '--' }}</small>
      </article>
      <article class="stat-tile glass-panel">
        <span>净资产</span>
        <strong class="numeric">{{ money(account.netAssets) }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>仓位</span>
        <strong class="numeric">{{ summary.ratioText }}</strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>持仓明细</h3></template>
      <el-table :data="filtered" stripe empty-text="暂无持仓">
        <el-table-column label="代码/名称" min-width="150">
          <template #default="{ row }">
            <strong>{{ posPair(row).symbol }}</strong>
            <span class="muted"> {{ row.symbolName || row.name || '' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="市场" width="80">
          <template #default="{ row }">
            <span class="mkt-tag" :class="`is-${posPair(row).market.toLowerCase()}`">{{ marketLabel(posPair(row).market) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.quantity ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column label="成本" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtNum(row.costPrice) }}</span></template>
        </el-table-column>
        <el-table-column label="现价" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtNum(row.last ?? row.currentPrice) }}</span></template>
        </el-table-column>
        <el-table-column label="盈亏" width="110" align="right">
          <template #default="{ row }">
            <span class="numeric" :class="changeClass(rowPnl(row))">{{ signedNum(rowPnl(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏%" width="90" align="right">
          <template #default="{ row }">
            <span :class="changeClass(rowPnlPct(row))">{{ fmtChange(rowPnlPct(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="市值占比" width="120">
          <template #default="{ row }">
            <div class="weight-bar"><i :style="{ width: weightPct(row) }" /></div>
            <span class="muted numeric">{{ weightPct(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(terminalRoute(posPair(row)))">详情</el-button>
            <el-button link type="primary" @click="$router.push(terminalRoute(posPair(row)))">交易</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <template #legend>
      <span class="legend-dots">
        <span><i class="dot-up" /> 涨红</span>
        <span><i class="dot-down" /> 跌绿</span>
      </span>
      <span>tabular-nums · glass-panel blur 12px · GET /trade/account + /trade/positions</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import TradeAuthBanner from '@/components/page/TradeAuthBanner.vue'
import { getTradeAccount, getTradePositions } from '@/api/trade'
import { changeClass, fmtChange, fmtNum } from '@/utils/format'
import { marketLabel, unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'
import { stubAccount, stubPositions } from '@/utils/stubs'
import { brokerAuthCode, cacheTradeAccount, cacheTradePositions, isBrokerAuthError, readCachedAccount, readCachedPositions } from '@/utils/tradeAuth'

const loading = ref(false)
const usingStub = ref(false)
const brokerAuth = ref(false)
const brokerCode = ref('')
const usingCache = ref(false)
const list = ref([])
const account = ref({})
const accounts = ref([])
const accountId = ref('')
const market = ref('')
const keyword = ref('')
const msg = ref('')
const currency = computed(() => account.value.currency || 'HKD')

function posPair(row) {
  const raw = String((row && row.symbol) || '').toUpperCase()
  let mkt = String((row && row.market) || '').toUpperCase()
  let symbol = raw
  if (raw.endsWith('.US')) { symbol = raw.slice(0, -3); mkt = 'US' }
  else if (raw.endsWith('.HK')) { symbol = raw.slice(0, -3); mkt = 'HK' }
  else if (raw.endsWith('.SH') || raw.endsWith('.SZ') || raw.endsWith('.SS')) { symbol = raw.split('.')[0]; mkt = 'CN' }
  if (!mkt) mkt = inferMarket(symbol)
  return { symbol, market: mkt }
}
function inferMarket(symbol) {
  if (/^\d{5,6}$/.test(symbol) || symbol.startsWith('00') || symbol.startsWith('30') || symbol.startsWith('60')) return symbol.length === 6 ? 'CN' : 'HK'
  return 'US'
}
function rowPx(row) {
  return Number(row.last ?? row.currentPrice ?? row.price)
}
function rowPnl(row) {
  const n = Number(row.pnl ?? row.unrealizedPnl)
  if (Number.isFinite(n)) return n
  const qty = Number(row.quantity)
  const cost = Number(row.costPrice)
  const px = rowPx(row)
  if ([qty, cost, px].every(Number.isFinite)) return (px - cost) * qty
  return NaN
}
function rowPnlPct(row) {
  const n = Number(row.pnlPct ?? row.pnlRate ?? row.unrealizedPnlRate)
  if (Number.isFinite(n)) return n
  const cost = Number(row.costPrice)
  const px = rowPx(row)
  if (cost && Number.isFinite(px)) return ((px / cost) - 1) * 100
  return NaN
}
function rowValue(row) {
  const qty = Number(row.quantity)
  const px = rowPx(row)
  if ([qty, px].every(Number.isFinite)) return qty * px
  return Number(row.marketValue) || 0
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return list.value.filter((row) => {
    const pair = posPair(row)
    const mktOk = !market.value || pair.market === market.value
    const textOk = !kw || `${pair.symbol} ${row.symbolName || ''} ${row.name || ''}`.toLowerCase().includes(kw)
    return mktOk && textOk
  })
})

const summary = computed(() => {
  const rows = filtered.value
  const marketValue = rows.reduce((s, r) => s + rowValue(r), 0)
  const unrealized = rows.reduce((s, r) => s + (Number.isFinite(rowPnl(r)) ? rowPnl(r) : 0), 0)
  const today = Number(account.value.todayPnl ?? account.value.dailyPnl)
  const todayPct = Number(account.value.todayPnlPct ?? account.value.dailyPnlPct)
  const net = Number(account.value.netAssets)
  const apiMv = Number(account.value.marketValue ?? account.value.totalMarketValue)
  const mv = Number.isFinite(apiMv) && !market.value && !keyword.value ? apiMv : marketValue
  const apiUn = Number(account.value.totalUnrealizedPnl ?? account.value.unrealizedPnl)
  const un = Number.isFinite(apiUn) && !market.value && !keyword.value ? apiUn : unrealized
  const ratio = Number(account.value.positionRatio)
  const ratioVal = Number.isFinite(ratio) ? ratio * (ratio > 1 ? 1 : 100) : net ? (mv / net) * 100 : 0
  return {
    marketValue: mv,
    todayPnl: Number.isFinite(today) ? today : un,
    todayPnlPct: Number.isFinite(todayPct) ? todayPct : (mv ? (un / mv) * 100 : 0),
    unrealized: un,
    unrealizedPct: Number(account.value.totalUnrealizedPnlPct) || (mv ? (un / mv) * 100 : 0),
    ratioText: Number.isFinite(ratioVal) ? `${ratioVal.toFixed(1)}%` : '--'
  }
})

function money(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return `${currency.value} ${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
function signedMoney(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  const sign = v > 0 ? '+' : v < 0 ? '-' : ''
  return `${sign}${currency.value} ${Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
function signedNum(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return '--'
  return `${v > 0 ? '+' : ''}${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
function weightPct(row) {
  const total = summary.value.marketValue
  if (!total) return '0%'
  return `${((rowValue(row) / total) * 100).toFixed(1)}%`
}

function applyStub() {
  usingStub.value = true
  usingCache.value = false
  account.value = stubAccount()
  list.value = stubPositions()
}

function applyBrokerAuth(err) {
  brokerAuth.value = true
  brokerCode.value = brokerAuthCode(err)
  const cachedRows = readCachedPositions()
  const cachedAcc = readCachedAccount()
  if (cachedRows.length || cachedAcc) {
    if (cachedRows.length) list.value = cachedRows
    if (cachedAcc) account.value = cachedAcc
    usingCache.value = true
    usingStub.value = false
    return
  }
  usingCache.value = false
  usingStub.value = false
  list.value = []
  msg.value = '长桥凭证不可用，未使用演示持仓以免误判空仓'
}

async function load() {
  loading.value = true
  brokerAuth.value = false
  usingCache.value = false
  try {
    const [posRes, accRes] = await Promise.allSettled([getTradePositions(), getTradeAccount()])
    const brokerErr = [posRes, accRes].find((r) => r.status === 'rejected' && isBrokerAuthError(r.reason))
    if (brokerErr) {
      applyBrokerAuth(brokerErr.reason)
      return
    }
    let live = false
    if (posRes.status === 'fulfilled') {
      const d = unwrap(posRes.value)
      const rows = d.positions || unwrapList(posRes.value)
      if (rows.length || d.configured) {
        list.value = rows
        cacheTradePositions(rows)
        msg.value = d.message || (d.configured === false ? '未配置长桥凭证' : '')
        live = true
      }
    }
    if (accRes.status === 'fulfilled') {
      const acc = unwrap(accRes.value)
      if (acc && (acc.netAssets != null || acc.availableCash != null || acc.currency)) {
        account.value = acc
        cacheTradeAccount(acc)
        const listAcc = acc.accounts || acc.items || []
        accounts.value = listAcc.map((a, i) => ({ id: a.id || a.accountId || String(i), label: a.name || a.accountName || `${a.currency || 'HKD'} 主账户` }))
        if (!accountId.value && accounts.value[0]) accountId.value = accounts.value[0].id
        live = true
      }
    }
    if (!live) applyStub()
    else usingStub.value = false
  } catch (e) {
    if (isBrokerAuthError(e)) applyBrokerAuth(e)
    else applyStub()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pos-stats { grid-template-columns: repeat(6, minmax(0, 1fr)); }
h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.weight-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--surface-muted);
  overflow: hidden;
  margin-bottom: 4px;
}
.weight-bar i {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--accent) 55%, transparent);
}
@media (max-width: 1100px) { .pos-stats { grid-template-columns: 1fr 1fr 1fr; } }
</style>
