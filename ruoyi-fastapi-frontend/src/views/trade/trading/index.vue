<template>
  <div class="app-container trading-desk">
    <div class="page-hero">
      <div>
        <h2>交易台</h2>
        <p>报价 · K线 · 买卖盘 · 成交明细 · 下单 · 委托（长桥）</p>
      </div>
      <div class="acts">
        <el-button @click="$router.push('/quant/longbridge')">长桥配置</el-button>
        <el-button @click="$router.push('/trade/risk')">风控</el-button>
        <el-button type="primary" :loading="loading" icon="Refresh" @click="refreshAll">刷新全部</el-button>
      </div>
    </div>
    <el-alert
      v-if="!configured"
      type="warning"
      show-icon
      class="mb12"
      title="长桥未配置或未连通：K线仍可走时序库，真实盘口/下单/持仓需先配置凭证"
    />

    <el-card shadow="never" class="mb12 quote-hero-card">
      <div class="quote-hero">
        <div class="hero-left">
          <el-input v-model="form.symbol" placeholder="代码" class="sym-input" @keyup.enter="onSymbolCommit" @change="onSymbolCommit">
            <template #append>
              <el-select v-model="form.market" style="width: 88px" @change="onSymbolCommit">
                <el-option label="US" value="US" />
                <el-option label="HK" value="HK" />
                <el-option label="CN" value="CN" />
              </el-select>
            </template>
          </el-input>
          <div class="hero-name">{{ quoteName }}</div>
        </div>
        <div class="hero-price" :class="quote.up ? 'up' : (quote.changeRate < 0 ? 'down' : '')">
          <div class="q-price">{{ fmt(quote.last || quote.price) }}</div>
          <div class="q-chg">{{ fmtSigned(quote.change) }} / {{ fmtPct(quote.changeRate) }}</div>
        </div>
        <div class="hero-ohlc">
          <span>开 {{ fmt(quote.open) }}</span>
          <span>高 {{ fmt(quote.high) }}</span>
          <span>低 {{ fmt(quote.low) }}</span>
          <span>量 {{ fmtVol(quote.volume) }}</span>
          <el-tag size="small" effect="plain">{{ quote.source || klineSource || '--' }}</el-tag>
        </div>
      </div>
      <div class="period-bar">
        <el-radio-group v-model="period" size="small" @change="loadKline">
          <el-radio-button v-for="p in periods" :key="p.value" :label="p.value">{{ p.label }}</el-radio-button>
        </el-radio-group>
        <span class="muted">{{ klineHint }}</span>
      </div>
      <div v-show="klineItems.length" v-loading="klineLoading" ref="chartRef" class="kline-chart"></div>
      <el-empty v-if="!klineLoading && !klineItems.length" :description="klineEmptyText" :image-size="56" />
    </el-card>

    <el-row :gutter="12">
      <el-col :lg="8" :xs="24">
        <el-card shadow="never" class="mb12 book-card">
          <template #header>
            <div class="hdr">
              <span>买卖盘</span>
              <span class="muted">{{ depthHint }}</span>
            </div>
          </template>
          <div v-if="showDepthEmpty" class="calm-empty">{{ depthEmptyText }}</div>
          <div v-else class="order-book">
            <div class="book-head"><span>卖盘</span><span>价格</span><span>数量</span></div>
            <div
              v-for="(row, idx) in displayAsks"
              :key="'a' + idx"
              class="book-row ask"
              @click="useBookPrice(row.price)"
            >
              <i class="vol-bar" :style="{ width: barWidth(row.volume, maxBookVol) }" />
              <span class="lv">{{ row.position || (displayAsks.length - idx) }}</span>
              <span class="px">{{ fmt(row.price) }}</span>
              <span class="sz">{{ fmtVol(row.volume) }}</span>
            </div>
            <div class="book-last" :class="quote.up ? 'up' : (quote.changeRate < 0 ? 'down' : '')">
              {{ fmt(quote.last || quote.price) }}
            </div>
            <div
              v-for="(row, idx) in displayBids"
              :key="'b' + idx"
              class="book-row bid"
              @click="useBookPrice(row.price)"
            >
              <i class="vol-bar" :style="{ width: barWidth(row.volume, maxBookVol) }" />
              <span class="lv">{{ row.position || idx + 1 }}</span>
              <span class="px">{{ fmt(row.price) }}</span>
              <span class="sz">{{ fmtVol(row.volume) }}</span>
            </div>
            <div class="book-head"><span>买盘</span><span>价格</span><span>数量</span></div>
          </div>
        </el-card>
      </el-col>
      <el-col :lg="8" :xs="24">
        <el-card shadow="never" class="mb12 tape-card">
          <template #header>
            <div class="hdr">
              <span>成交明细</span>
              <span class="muted">{{ tapeHint }}</span>
            </div>
          </template>
          <div v-if="showTapeEmpty" class="calm-empty">{{ tapeEmptyText }}</div>
          <el-table v-else :data="trades" size="small" max-height="360" empty-text="暂无成交">
            <el-table-column label="时间" width="92">
              <template #default="{ row }">{{ fmtTime(row.time) }}</template>
            </el-table-column>
            <el-table-column label="价格" width="88">
              <template #default="{ row }">
                <span :class="sideClass(row.side)">{{ fmt(row.price) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="数量">
              <template #default="{ row }">{{ fmtVol(row.volume || row.size) }}</template>
            </el-table-column>
            <el-table-column label="方向" width="56">
              <template #default="{ row }">{{ sideLabel(row.side) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :lg="8" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>下单面板</template>
          <el-form label-width="72px">
            <el-form-item label="市场">
              <el-select v-model="form.market" style="width: 100%" @change="onSymbolCommit">
                <el-option label="US" value="US" />
                <el-option label="HK" value="HK" />
                <el-option label="CN" value="CN" />
              </el-select>
            </el-form-item>
            <el-form-item label="代码"><el-input v-model="form.symbol" @change="onSymbolCommit" /></el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="form.side">
                <el-radio-button label="buy">买入</el-radio-button>
                <el-radio-button label="sell">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="form.orderType" style="width: 100%">
                <el-option label="限价 LO" value="LO" />
                <el-option label="市价 MO" value="MO" />
              </el-select>
            </el-form-item>
            <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" style="width: 100%" /></el-form-item>
            <el-form-item v-if="form.orderType === 'LO'" label="价格">
              <el-input-number v-model="form.price" :min="0.01" :step="0.01" style="width: 100%" />
              <el-button link type="primary" @click="form.price = Number(quote.last || quote.price || form.price)">用现价</el-button>
            </el-form-item>
            <el-form-item label="预估">
              <span class="muted">名义金额 ≈ {{ notional }} · 可用 {{ availableCashText }}</span>
            </el-form-item>
            <el-button type="primary" style="width: 100%" :loading="submitting" :disabled="!configured" @click="submit">
              提交订单
            </el-button>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :lg="8" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>资金</template>
          <el-table :data="account.balances || []" size="small" empty-text="暂无">
            <el-table-column prop="currency" label="币种" width="70" />
            <el-table-column prop="netAssets" label="净资产" />
            <el-table-column prop="availableCash" label="可用" />
            <el-table-column prop="buyPower" label="购买力" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :lg="16" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>
            <div class="hdr">
              <span>持仓快照</span>
              <el-button link type="primary" @click="$router.push('/trade/positions')">全部</el-button>
            </div>
          </template>
          <el-table :data="positions" size="small" max-height="220" empty-text="暂无持仓" @row-click="fillFromPos">
            <el-table-column prop="symbol" label="代码" width="110" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="costPrice" label="成本" width="90" />
            <el-table-column prop="marketValue" label="市值" width="100" />
            <el-table-column label="操作" width="70">
              <template #default="{ row }"><el-button link type="primary" @click.stop="fillFromPos(row)">填入</el-button></template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="hdr">
          <span>委托</span>
          <div class="order-tools">
            <el-checkbox v-model="onlyCurrentSymbol">仅当前标的</el-checkbox>
            <el-radio-group v-model="orderScope" size="small" @change="loadOrders">
              <el-radio-button label="today">今日</el-radio-button>
              <el-radio-button label="history">历史</el-radio-button>
            </el-radio-group>
            <el-button link type="primary" class="ml8" @click="$router.push('/trade/orders')">全部</el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="visibleOrders" size="small" max-height="280">
        <el-table-column prop="symbol" label="标的" width="110" />
        <el-table-column prop="side" label="方向" width="80" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="quantity" label="量" width="80" />
        <el-table-column prop="price" label="价" width="90" />
        <el-table-column prop="executedQuantity" label="已成" width="80" />
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button v-if="row.orderId && orderScope === 'today'" link type="danger" @click="cancel(row)">撤</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
<script setup name="TradeTrading">
import echarts from '@/utils/echarts'
import { applyChartTheme } from '@/utils/echartsTheme'
import {
  getTradeAccount,
  getTradeOrders,
  getTradePositions,
  submitTradeOrder,
  cancelTradeOrder,
  getTradeQuoteDepth,
  getTradeQuoteTrades,
  getTradeQuoteKline
} from '@/api/trade'

const route = useRoute()
const router = useRouter()
const { proxy } = getCurrentInstance()
const loading = ref(false)
const submitting = ref(false)
const klineLoading = ref(false)
const account = ref({ balances: [] })
const orders = ref([])
const positions = ref([])
const configured = ref(true)
const orderScope = ref('today')
const onlyCurrentSymbol = ref(true)
const period = ref('daily')
const periods = [
  { value: 'intraday', label: '分时' },
  { value: '1min', label: '1分' },
  { value: '5min', label: '5分' },
  { value: '15min', label: '15分' },
  { value: 'daily', label: '日K' },
  { value: 'weekly', label: '周K' },
  { value: 'monthly', label: '月K' }
]
const form = ref({
  symbol: 'AAPL',
  market: 'US',
  side: 'buy',
  orderType: 'LO',
  quantity: 1,
  price: 100
})
applyRouteSymbol(route.query.symbol, route.query.market)
const quote = ref({})
const klineItems = ref([])
const klineSource = ref('')
const klineMessage = ref('')
const asks = ref([])
const bids = ref([])
const trades = ref([])
const depthMeta = ref({})
const tapeMeta = ref({})
const chartRef = ref(null)
let chart = null
let liveTimer = null
const liveBlocked = ref(false)
const LIVE_MS = 20000
const LIVE_SLOW_MS = 60000

function isCircuit(data) {
  const reason = data && data.reason
  return reason === 'circuit_open' || reason === 'unauthorized'
}

const notional = computed(() => {
  const p = form.value.orderType === 'MO' ? Number(quote.value.last || quote.value.price || 0) : Number(form.value.price || 0)
  return (p * Number(form.value.quantity || 0)).toFixed(2)
})
const availableCashText = computed(() => {
  const b = (account.value.balances || [])[0]
  return b ? `${b.availableCash || '--'} ${b.currency || ''}` : '--'
})
const isCn = computed(() => String(form.value.market || '').toUpperCase() === 'CN')
const quoteName = computed(() => `${form.value.symbol || '--'} · ${form.value.market || '--'}`)
const displayAsks = computed(() => [...asks.value].slice(0, 10).reverse())
const displayBids = computed(() => bids.value.slice(0, 10))
const maxBookVol = computed(() => {
  const vols = [...asks.value, ...bids.value].map(r => Number(r.volume || 0)).filter(n => Number.isFinite(n))
  return vols.length ? Math.max(...vols) : 0
})
const showDepthEmpty = computed(() => !asks.value.length && !bids.value.length)
const showTapeEmpty = computed(() => !trades.value.length)
const depthEmptyText = computed(() => depthMeta.value.message || (isCn.value ? 'A股暂无实时盘口' : '暂无盘口'))
const tapeEmptyText = computed(() => tapeMeta.value.message || (isCn.value ? 'A股暂无实时盘口' : '暂无成交'))
const depthHint = computed(() => (depthMeta.value.available ? `${asks.value.length}档卖 / ${bids.value.length}档买` : '实时'))
const tapeHint = computed(() => (trades.value.length ? `${trades.value.length} 笔` : ''))
const klineHint = computed(() => {
  if (!klineItems.value.length) return ''
  return `${klineItems.value.length} 根 · ${klineSource.value || '--'}`
})
const klineEmptyText = computed(() => klineMessage.value || '暂无K线（不补造）')
const visibleOrders = computed(() => {
  if (!onlyCurrentSymbol.value) return orders.value
  return orders.value.filter(row => orderMatches(row.symbol))
})

function applyRouteSymbol(rawSymbol, rawMarket) {
  const parsed = parseSymbolMarket(rawSymbol, rawMarket || form.value.market)
  form.value.symbol = parsed.symbol
  form.value.market = parsed.market
}
function parseSymbolMarket(raw, fallbackMarket = 'US') {
  const text = String(raw || '').trim().toUpperCase()
  if (!text) return { symbol: form.value.symbol, market: fallbackMarket || 'US' }
  if (text.includes('.')) {
    const idx = text.lastIndexOf('.')
    const code = text.slice(0, idx)
    const suffix = text.slice(idx + 1)
    if (['US', 'HK', 'SH', 'SZ'].includes(suffix)) {
      return { symbol: code, market: suffix === 'SH' || suffix === 'SZ' ? 'CN' : suffix }
    }
  }
  return { symbol: text, market: String(fallbackMarket || 'US').toUpperCase() }
}
function orderMatches(symbol) {
  const s = String(symbol || '').toUpperCase()
  const cur = String(form.value.symbol || '').toUpperCase()
  const mkt = String(form.value.market || '').toUpperCase()
  if (!cur) return true
  return s === cur || s === `${cur}.${mkt}` || s.startsWith(`${cur}.`)
}
function fmt(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : String(v)
}
function fmtSigned(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}`
}
function fmtPct(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function fmtVol(v) {
  if (v === null || v === undefined || v === '') return '--'
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n >= 1 ? n.toFixed(0) : n.toFixed(2)
}
function fmtTime(v) {
  const text = String(v || '')
  return text.length >= 19 ? text.slice(11, 19) : text || '--'
}
function sideLabel(side) {
  if (side === 'buy') return '买'
  if (side === 'sell') return '卖'
  return '--'
}
function sideClass(side) {
  if (side === 'buy') return 'up'
  if (side === 'sell') return 'down'
  return ''
}
function barWidth(vol, max) {
  const n = Number(vol || 0)
  if (!max || !n) return '0%'
  return Math.max(6, Math.round((n / max) * 100)) + '%'
}
function useBookPrice(price) {
  const n = Number(price)
  if (Number.isFinite(n) && n > 0) form.value.price = n
}
function onSymbolCommit() {
  const parsed = parseSymbolMarket(form.value.symbol, form.value.market)
  form.value.symbol = parsed.symbol
  form.value.market = parsed.market
  router.replace({ path: '/trade/trading', query: { symbol: parsed.symbol, market: parsed.market } })
  loadQuoteBoard()
  restartLive()
}
function fillFromPos(row) {
  const parsed = parseSymbolMarket(row.symbol, form.value.market)
  form.value.symbol = parsed.symbol
  form.value.market = parsed.market
  form.value.side = 'sell'
  if (row.quantity) form.value.quantity = Number(row.quantity) || form.value.quantity
  onSymbolCommit()
}
function applyQuote(q) {
  if (!q || (!q.last && !q.price && !q.close)) return
  const last = q.last != null ? q.last : q.price != null ? q.price : q.close
  const rate = q.changeRate
  quote.value = {
    ...quote.value,
    ...q,
    last,
    price: last,
    up: Number(rate) > 0,
    changeRate: rate,
    source: q.source || quote.value.source
  }
  if (form.value.orderType === 'LO' && (form.value.price == null || form.value.price === 100)) {
    const n = Number(last)
    if (Number.isFinite(n) && n > 0) form.value.price = n
  }
}
async function loadKline(options = {}) {
  if (!form.value.symbol) return
  const showOverlay = !options.skipPageLoading
  if (showOverlay) proxy.$modal.loading('行情加载中…')
  klineLoading.value = true
  try {
    const res = await getTradeQuoteKline({
      symbol: form.value.symbol,
      market: form.value.market,
      period: period.value,
      limit: period.value === 'intraday' ? 400 : 200
    })
    const data = res.data || {}
    klineItems.value = data.klines || []
    klineSource.value = data.source || ''
    klineMessage.value = data.message || ''
    if (data.configured === false) configured.value = false
    if (data.quote) applyQuote(data.quote)
    await nextTick()
    renderChart()
  } catch (e) {
    klineItems.value = []
    klineMessage.value = 'K线加载失败'
    renderChart()
  } finally {
    klineLoading.value = false
    if (showOverlay) proxy.$modal.closeLoading()
  }
}
async function loadDepth() {
  try {
    const res = await getTradeQuoteDepth({ symbol: form.value.symbol, market: form.value.market })
    const data = res.data || {}
    asks.value = data.asks || []
    bids.value = data.bids || []
    depthMeta.value = data
    if (data.configured === false) configured.value = false
    if (isCircuit(data)) liveBlocked.value = true
    if (data.last) applyQuote({ last: data.last, source: 'longbridge' })
  } catch (e) {
    asks.value = []
    bids.value = []
    depthMeta.value = { message: isCn.value ? 'A股暂无实时盘口' : '盘口加载失败' }
  }
}
async function loadTrades() {
  try {
    const res = await getTradeQuoteTrades({ symbol: form.value.symbol, market: form.value.market, count: 40 })
    const data = res.data || {}
    trades.value = data.trades || []
    tapeMeta.value = data
    if (data.configured === false) configured.value = false
    if (isCircuit(data)) liveBlocked.value = true
  } catch (e) {
    trades.value = []
    tapeMeta.value = { message: isCn.value ? 'A股暂无实时盘口' : '成交明细加载失败' }
  }
}
async function loadQuoteBoard() {
  await proxy.$modal.withLoading('行情加载中…', async () => {
    await Promise.all([
      loadKline({ skipPageLoading: true }),
      loadDepth(),
      loadTrades()
    ])
  })
}
function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const items = klineItems.value || []
  if (!items.length) {
    chart.clear()
    return
  }
  const dates = items.map(i => i.date)
  const isLine = period.value === 'intraday'
  const up = '#f56c6c'
  const down = '#67c23a'
  const series = isLine
    ? [{
        name: '分时',
        type: 'line',
        data: items.map(i => i.close),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: up },
        areaStyle: { opacity: 0.12, color: up }
      }]
    : [{
        name: 'K线',
        type: 'candlestick',
        data: items.map(i => [i.open, i.close, i.low, i.high]),
        itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down }
      }]
  series.push({
    name: '成交量',
    type: 'bar',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: items.map(i => ({
      value: i.volume,
      itemStyle: { color: Number(i.close) >= Number(i.open) ? up : down }
    }))
  })
  const option = applyChartTheme({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 48, right: 16, top: 24, height: '58%' },
      { left: 48, right: 16, top: '78%', height: '14%' }
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: !isLine, axisLine: { onZero: false } },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: !isLine, axisLabel: { show: false }, axisTick: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: isLine ? 0 : 55, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 4, height: 16, start: isLine ? 0 : 55, end: 100 }
    ],
    series
  })
  chart.setOption(option, true)
}
async function loadOrders() {
  const o = await getTradeOrders(orderScope.value)
  orders.value = (o.data && o.data.orders) || []
  if (o.data && o.data.configured === false) configured.value = false
}
async function refreshAll() {
  liveBlocked.value = false
  loading.value = true
  try {
    const [a, p] = await Promise.all([
      getTradeAccount(),
      getTradePositions(),
      loadOrders(),
      loadQuoteBoard()
    ])
    account.value = a.data || { balances: [] }
    configured.value = account.value.configured !== false
    positions.value = (p.data && p.data.positions) || []
    restartLive()
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (!form.value.symbol || !form.value.quantity) return proxy.$modal.msgError('请填写代码和数量')
  await proxy.$modal.confirm(`确认${form.value.side === 'buy' ? '买入' : '卖出'} ${form.value.symbol} x ${form.value.quantity}？`)
  submitting.value = true
  try {
    const res = await submitTradeOrder(form.value)
    const d = res.data || {}
    d.ok ? proxy.$modal.msgSuccess(d.message || '已提交') : proxy.$modal.msgError(d.message || '失败')
    await refreshAll()
  } finally {
    submitting.value = false
  }
}
async function cancel(row) {
  await proxy.$modal.confirm('撤单 ' + row.orderId + '？')
  const res = await cancelTradeOrder(row.orderId)
  const d = res.data || {}
  d.ok ? proxy.$modal.msgSuccess(d.message || '已撤') : proxy.$modal.msgError(d.message || '失败')
  await refreshAll()
}
function stopLive() {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
}
function tickLive() {
  loadKline()
  if (!isCn.value && configured.value && !liveBlocked.value) {
    loadDepth()
    loadTrades()
  }
}
function startLive() {
  stopLive()
  if (document.hidden) return
  const ms = liveBlocked.value ? LIVE_SLOW_MS : LIVE_MS
  liveTimer = setInterval(tickLive, ms)
}
function restartLive() {
  startLive()
}
function handleVisibility() {
  if (document.visibilityState === 'visible') {
    if (!liveTimer) {
      tickLive()
      startLive()
    }
  } else {
    stopLive()
  }
}
function handleResize() {
  chart && chart.resize()
}
watch(
  () => [route.query.symbol, route.query.market],
  ([sym, mkt]) => {
    if (!sym) return
    const parsed = parseSymbolMarket(sym, mkt || form.value.market)
    if (parsed.symbol === form.value.symbol && parsed.market === form.value.market) return
    form.value.symbol = parsed.symbol
    form.value.market = parsed.market
    loadQuoteBoard()
    restartLive()
  }
)
onMounted(() => {
  refreshAll()
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('visibilitychange', handleVisibility)
  stopLive()
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>
<style scoped>
.page-hero { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.page-hero h2 { margin: 0 0 4px; color: var(--text-emphasis); }
.page-hero p { margin: 0; color: var(--text-muted); font-size: 13px; }
.acts { display: flex; gap: 8px; flex-wrap: wrap; }
.mb12 { margin-bottom: 12px; }
.ml8 { margin-left: 8px; }
.muted { color: var(--text-muted); font-size: 12px; }
.hdr { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.quote-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.sym-input { width: 260px; max-width: 100%; }
.hero-name { margin-top: 6px; color: var(--text-muted); font-size: 13px; }
.hero-price { text-align: right; }
.q-price { font-size: 32px; font-weight: 800; line-height: 1.1; }
.q-chg { margin-top: 4px; font-size: 14px; }
.hero-ohlc {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.period-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
.kline-chart { width: 100%; height: 360px; }
.up { color: var(--stat-up, #f87171); }
.down { color: var(--stat-down, #34d399); }
.calm-empty {
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
  padding: 16px;
  text-align: center;
}
.order-book { position: relative; font-size: 13px; }
.book-head, .book-row {
  display: grid;
  grid-template-columns: 36px 1fr 1fr;
  gap: 8px;
  padding: 4px 6px;
  position: relative;
}
.book-head { color: var(--text-muted); font-size: 12px; }
.book-row { cursor: pointer; border-radius: 4px; }
.book-row:hover { background: var(--surface-hover); }
.book-row .vol-bar {
  position: absolute;
  right: 0;
  top: 2px;
  bottom: 2px;
  opacity: 0.16;
  border-radius: 3px;
}
.book-row.ask .vol-bar { background: var(--stat-up, #f87171); }
.book-row.bid .vol-bar { background: var(--stat-down, #34d399); }
.book-row.ask .px { color: var(--stat-up, #f87171); }
.book-row.bid .px { color: var(--stat-down, #34d399); }
.book-last {
  text-align: center;
  font-weight: 800;
  font-size: 18px;
  padding: 8px 0;
  border-top: 1px dashed var(--border-glass);
  border-bottom: 1px dashed var(--border-glass);
  margin: 4px 0;
}
.order-tools { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
</style>
