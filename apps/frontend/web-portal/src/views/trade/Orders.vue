<template>
  <PageFrame
    title="委托"
    :subtitle="scopeHint"
    :loading="loading"
  >
    <template #actions>
      <el-radio-group v-model="scope" @change="load">
        <el-radio-button value="today">今日</el-radio-button>
        <el-radio-button value="7d">近7日</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <TradeAuthBanner :visible="brokerAuth" :code="brokerCode" />
    <el-alert v-if="usingStub && !brokerAuth" title="STUB · stubOrders" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="loadError && !brokerAuth" :title="loadError" type="error" show-icon :closable="false" />
    <el-alert v-else-if="msg && !brokerAuth" :title="msg" type="info" show-icon :closable="false" />

    <div class="toolbar">
      <div class="chip-row">
        <button
          v-for="tab in statusTabs"
          :key="tab.key"
          type="button"
          class="filter-chip"
          :class="{ active: status === tab.key }"
          @click="status = tab.key"
        >{{ tab.label }}</button>
      </div>
      <el-input v-model="keyword" clearable placeholder="代码 / 订单号" style="width:220px" :prefix-icon="Search" />
    </div>

    <p class="summary-line">
      <span class="numeric">{{ filtered.length }}</span> 笔
      <span class="dot">·</span>
      <span class="numeric">{{ cancelableCount }}</span> 可撤
    </p>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无委托">
        <el-table-column label="时间" width="100">
          <template #default="{ row }"><span class="numeric">{{ timeText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="方向" width="88">
          <template #default="{ row }">
            <span class="ord-side" :class="isBuy(row) ? 'is-buy' : 'is-sell'">{{ sideLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="代码" width="100">
          <template #default="{ row }"><strong>{{ orderPair(row).symbol }}</strong></template>
        </el-table-column>
        <el-table-column label="名称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.stockName || row.symbolName || row.name || '--' }}</template>
        </el-table-column>
        <el-table-column label="数量" width="80" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.quantity ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column label="价格" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtNum(row.price) }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="ord-status" :class="`is-${statusKey(row)}`">{{ statusLabelOf(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="88">
          <template #default="{ row }">{{ typeLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="128">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="canCancel(row)" link type="danger" @click="cancel(row)">撤单</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawer" :title="detailTitle" size="420px">
      <template v-if="current">
        <dl class="detail-dl">
          <div><dt>订单号</dt><dd class="numeric">{{ current.orderId || current.id || '--' }}</dd></div>
          <div><dt>时间</dt><dd class="numeric">{{ timeText(current) }}</dd></div>
          <div><dt>方向</dt><dd><span class="ord-side" :class="isBuy(current) ? 'is-buy' : 'is-sell'">{{ sideLabel(current) }}</span></dd></div>
          <div><dt>代码</dt><dd>{{ orderPair(current).symbol }} {{ current.stockName || current.name || '' }}</dd></div>
          <div><dt>数量 / 价格</dt><dd class="numeric">{{ current.quantity ?? '--' }} / {{ fmtNum(current.price) }}</dd></div>
          <div><dt>成交</dt><dd class="numeric">{{ current.executedQuantity ?? 0 }} / {{ fmtNum(current.executedPrice) }}</dd></div>
          <div><dt>状态</dt><dd><span class="ord-status" :class="`is-${statusKey(current)}`">{{ statusLabelOf(current) }}</span></dd></div>
          <div><dt>类型</dt><dd>{{ typeLabel(current) }}</dd></div>
          <div v-if="current.remark"><dt>备注</dt><dd>{{ current.remark }}</dd></div>
        </dl>
        <div class="drawer-acts">
          <el-button type="primary" @click="$router.push(terminalRoute(orderPair(current)))">前往终端</el-button>
          <el-button v-if="canCancel(current)" type="danger" plain @click="cancel(current)">撤单</el-button>
        </div>
      </template>
    </el-drawer>

    <template #legend>
      <span class="legend-dots">
        <span><i class="dot-up" /> 买入红</span>
        <span><i class="dot-down" /> 卖出绿</span>
      </span>
      <span>tabular-nums · glass-panel · GET /trade/orders · POST /trade/order/:id/cancel</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import TradeAuthBanner from '@/components/page/TradeAuthBanner.vue'
import { cancelTradeOrder, getTradeOrders } from '@/api/trade'
import { fmtNum } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'
import { brokerAuthCode, isBrokerAuthError } from '@/utils/tradeAuth'
import { useUserStore } from '@/store/user'
import { errorText, isDemoSession, stubOrders } from '@/utils/stubs'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const OPEN_STATUS = new Set(['submitted', 'new', 'wait_to_new', 'waittonew', 'partial_filled', 'partialfilled', 'wait_to_cancel', 'waittocancel', 'pending', 'partial', 'open', 'not_reported', 'notreported'])
const OPEN_LABEL = new Set(['已提交', '待成交', '待报', '待撤', '部分成交'])
const STATUS_TABS = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待成交' },
  { key: 'filled', label: '已成交' },
  { key: 'partial', label: '部分成交' },
  { key: 'cancelled', label: '已撤销' },
  { key: 'rejected', label: '已拒绝' }
]

const loading = ref(false)
const usingStub = ref(false)
const brokerAuth = ref(false)
const brokerCode = ref('')
const scope = ref('today')
const status = ref('')
const keyword = ref('')
const list = ref([])
const msg = ref('')
const loadError = ref('')
const drawer = ref(false)
const current = ref(null)
const statusTabs = STATUS_TABS

const scopeHint = computed(() => {
  if (scope.value === '7d') return '近7日委托 · 状态筛选 · 撤单与详情 · 对齐 /trade/orders'
  if (scope.value === 'all') return '全部委托 · 状态筛选 · 撤单与详情 · 对齐 /trade/orders'
  return '当日委托 · 状态筛选 · 撤单与详情 · 对齐 /trade/orders'
})

function orderLooksOpen(row) {
  if (!row) return false
  if (row.open === true) return true
  const compact = String(row.status || '').trim().toLowerCase().replace(/[\s-]/g, '_')
  if (OPEN_STATUS.has(compact) || OPEN_STATUS.has(compact.replace(/_/g, ''))) return true
  return OPEN_LABEL.has(String(row.statusLabel || '').trim())
}

function statusLabelOf(row) {
  const raw = String(row?.statusLabel || '').trim()
  if (raw) {
    if (raw === '已撤') return '已撤销'
    if (raw === '已提交' || raw === '待报') return '待成交'
    return raw
  }
  return ({
    pending: '待成交',
    filled: '已成交',
    partial: '部分成交',
    cancelled: '已撤销',
    rejected: '已拒绝'
  })[statusKey(row)] || row?.status || '--'
}

function statusKey(row) {
  const compact = String(row?.status || '').toLowerCase().replace(/[\s_-]/g, '')
  const label = String(row?.statusLabel || '')
  if (compact.includes('partial') || label.includes('部分')) return 'partial'
  if (compact.includes('reject') || compact.includes('expire') || label.includes('拒绝') || label.includes('过期')) return 'rejected'
  if (compact.includes('cancel') || label.includes('撤') || label.includes('取消')) return 'cancelled'
  if (compact.includes('fill') || label.includes('已成交')) return 'filled'
  if (orderLooksOpen(row) || compact.includes('pending') || compact.includes('submit') || compact.includes('new') || label.includes('待')) return 'pending'
  return 'other'
}

function canCancel(row) {
  const key = statusKey(row)
  return Boolean(row && (row.orderId || row.id) && (key === 'pending' || key === 'partial'))
}

function isBuy(row) {
  const s = String(row?.side || '').toLowerCase()
  return s === 'buy' || s === 'b' || s.includes('买')
}

function sideLabel(row) {
  return isBuy(row) ? '买入' : '卖出'
}

function typeLabel(row) {
  const raw = String(row?.orderType || row?.type || '').toUpperCase()
  if (!raw) return '--'
  if (['LO', 'LIMIT', '限价'].includes(raw) || raw.includes('限')) return '限价'
  if (['MO', 'MARKET', '市价'].includes(raw) || raw.includes('市')) return '市价'
  if (raw === 'ELO') return '增强限价'
  if (raw === 'AO') return '竞价'
  return row.orderType || raw
}

function orderPair(row) {
  const raw = String((row && row.symbol) || '').toUpperCase()
  let mkt = String((row && row.market) || '').toUpperCase()
  let symbol = raw
  if (raw.endsWith('.US')) { symbol = raw.slice(0, -3); mkt = 'US' }
  else if (raw.endsWith('.HK')) { symbol = raw.slice(0, -3); mkt = 'HK' }
  else if (raw.endsWith('.SH') || raw.endsWith('.SZ') || raw.endsWith('.SS')) { symbol = raw.split('.')[0]; mkt = 'CN' }
  if (!mkt) {
    if (/^\d{5,6}$/.test(symbol) || symbol.startsWith('00') || symbol.startsWith('30') || symbol.startsWith('60')) mkt = symbol.length === 6 ? 'CN' : 'HK'
    else mkt = 'US'
  }
  return { symbol, market: mkt }
}

function parseWhen(row) {
  const raw = row?.submittedAt || row?.updatedAt || row?.createTime || row?.time || ''
  const text = String(raw).trim()
  if (!text) return null
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(text)) {
    const [h, m, s] = text.split(':').map(Number)
    const d = new Date()
    d.setHours(h, m || 0, s || 0, 0)
    return d
  }
  const d = new Date(text.replace(' ', 'T'))
  return Number.isNaN(d.getTime()) ? null : d
}

function timeText(row) {
  const d = parseWhen(row)
  if (d) {
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    if (scope.value === 'today') return `${hh}:${mm}:${ss}`
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${mo}-${day} ${hh}:${mm}`
  }
  const raw = String(row?.submittedAt || row?.updatedAt || row?.time || '').trim()
  return raw.slice(-8) || '--'
}

function withinDays(row, days) {
  const d = parseWhen(row)
  if (!d) return true
  return Date.now() - d.getTime() <= days * 86400000
}

function pickOrders(res) {
  const d = unwrap(res)
  const rows = d.orders || unwrapList(res)
  return { rows: Array.isArray(rows) ? rows : [], data: d }
}

function mergeById(a, b) {
  const map = new Map()
  for (const row of [...a, ...b]) {
    const key = String(row.orderId || row.id || `${row.symbol}-${row.submittedAt}-${row.price}`)
    if (!map.has(key)) map.set(key, row)
  }
  return [...map.values()]
}

const scoped = computed(() => {
  if (scope.value === '7d') return list.value.filter((row) => withinDays(row, 7))
  return list.value
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return scoped.value.filter((row) => {
    const keyOk = !status.value || statusKey(row) === status.value
    const pair = orderPair(row)
    const text = `${pair.symbol} ${row.stockName || ''} ${row.name || ''} ${row.orderId || ''} ${row.id || ''}`.toLowerCase()
    return keyOk && (!kw || text.includes(kw))
  })
})

const cancelableCount = computed(() => filtered.value.filter(canCancel).length)
const detailTitle = computed(() => {
  if (!current.value) return '委托详情'
  const pair = orderPair(current.value)
  return `${pair.symbol} ${current.value.stockName || current.value.name || ''}`.trim()
})

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  list.value = stubOrders()
  msg.value = ''
  loadError.value = ''
}

async function load() {
  if (demoMode()) {
    applyStub()
    return
  }
  loading.value = true
  brokerAuth.value = false
  usingStub.value = false
  loadError.value = ''
  msg.value = ''
  try {
    if (scope.value === 'today') {
      const res = await getTradeOrders('today')
      const { rows, data } = pickOrders(res)
      list.value = rows
      msg.value = data.message || (data.configured === false ? '未配置长桥凭证' : '')
      return
    }
    const [histRes, todayRes] = await Promise.allSettled([getTradeOrders('history'), getTradeOrders('today')])
    let rows = []
    let message = ''
    const errors = []
    if (histRes.status === 'fulfilled') {
      const { rows: hist, data } = pickOrders(histRes.value)
      rows = hist
      message = data.message || (data.configured === false ? '未配置长桥凭证' : '')
    } else if (isBrokerAuthError(histRes.reason)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(histRes.reason)
    } else errors.push(errorText(histRes.reason, '历史委托加载失败'))
    if (todayRes.status === 'fulfilled') {
      const { rows: today } = pickOrders(todayRes.value)
      rows = mergeById(today, rows)
    } else if (isBrokerAuthError(todayRes.reason)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(todayRes.reason)
    } else errors.push(errorText(todayRes.reason, '今日委托加载失败'))
    list.value = rows
    msg.value = message
    if (errors.length) loadError.value = errors.join('；')
  } catch (e) {
    if (isBrokerAuthError(e)) {
      brokerAuth.value = true
      brokerCode.value = brokerAuthCode(e)
      list.value = []
      msg.value = ''
    } else {
      list.value = []
      loadError.value = errorText(e, '委托加载失败')
    }
  } finally {
    loading.value = false
  }
}

function openDetail(row) {
  current.value = row
  drawer.value = true
}

async function cancel(row) {
  const oid = row.orderId || row.id
  await ElMessageBox.confirm(`确认撤单 ${oid}？`, '委托')
  if (usingStub.value) {
    const next = { ...row, status: 'cancelled', statusLabel: '已撤销', open: false }
    list.value = list.value.map((item) => ((item.orderId || item.id) === oid ? next : item))
    if (current.value && (current.value.orderId || current.value.id) === oid) current.value = next
    ElMessage.success('已撤（STUB）')
    return
  }
  const res = await cancelTradeOrder(oid)
  const d = res.data || {}
  if (d.ok !== false) ElMessage.success(d.message || '已撤')
  else ElMessage.error(d.message || '失败')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.summary-line {
  margin: 0 0 10px;
  color: var(--text-secondary);
  font-size: 13px;
}
.summary-line .dot { margin: 0 6px; opacity: 0.6; }
.ord-side,
.ord-status {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.ord-side.is-buy {
  color: var(--order-buy-solid);
  background: color-mix(in srgb, var(--stat-up) var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, var(--stat-up) var(--chip-line), transparent);
}
.ord-side.is-sell {
  color: var(--order-sell-solid);
  background: color-mix(in srgb, var(--stat-down) var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, var(--stat-down) var(--chip-line), transparent);
}
.ord-status.is-pending {
  color: #d97706;
  background: color-mix(in srgb, #f59e0b var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, #f59e0b var(--chip-line), transparent);
}
.ord-status.is-filled {
  color: var(--order-sell-solid);
  background: color-mix(in srgb, var(--stat-down) var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, var(--stat-down) var(--chip-line), transparent);
}
.ord-status.is-partial {
  color: #2563eb;
  background: color-mix(in srgb, #3b82f6 var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, #3b82f6 var(--chip-line), transparent);
}
.ord-status.is-cancelled,
.ord-status.is-other {
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) var(--chip-fill), transparent);
  border: 1px solid var(--control-border);
}
.ord-status.is-rejected {
  color: var(--order-buy-solid);
  background: color-mix(in srgb, var(--stat-up) var(--chip-fill), transparent);
  border: 1px solid color-mix(in srgb, var(--stat-up) var(--chip-line), transparent);
}
.detail-dl { display: grid; gap: 10px; margin: 0 0 16px; }
.detail-dl div { display: grid; grid-template-columns: 88px 1fr; gap: 8px; align-items: center; }
.detail-dl dt { color: var(--text-secondary); font-size: 12px; }
.detail-dl dd { margin: 0; }
.drawer-acts { display: flex; gap: 8px; }
</style>
