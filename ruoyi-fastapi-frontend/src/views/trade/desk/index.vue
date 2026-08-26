<template>
  <div class="desk-page">
    <div class="desk-top">
      <div>
        <h2>交易工作台</h2>
        <p>自选 · 行情K线 · 盘口挂单 · 快捷交易 · 量化 · AI（长桥）</p>
      </div>
      <div class="acts">
        <el-tag :type="configured ? 'success' : 'warning'" effect="plain">{{ configured ? '长桥已连接' : '长桥未就绪' }}</el-tag>
        <el-button @click="$router.push('/quant/longbridge')">凭证</el-button>
        <el-button @click="$router.push('/quant/strategy-config')">策略开关</el-button>
        <el-button type="primary" :loading="loading" icon="Refresh" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <div class="desk-grid">
      <aside class="pane watch-pane">
        <div class="pane-h">
          <span>自选清单</span>
          <el-button link type="primary" @click="loadWatch">刷新</el-button>
        </div>
        <el-input v-model="watchKw" size="small" clearable placeholder="过滤代码/名称" class="mb8" />
        <div class="watch-list" v-loading="watchLoading">
          <div
            v-for="row in filteredWatch"
            :key="row.symbol + row.market"
            class="watch-row"
            :class="{ active: isActive(row) }"
            @click="selectWatch(row)"
          >
            <div>
              <div class="sym">{{ row.symbol }}</div>
              <div class="nm">{{ row.name || row.market }}</div>
            </div>
            <div class="px" :class="chgClass(row.changeRate)">
              <div>{{ fmt(row.price) }}</div>
              <div class="chg">{{ fmtPct(row.changeRate) }}</div>
            </div>
          </div>
          <el-empty v-if="!filteredWatch.length && !watchLoading" description="暂无自选，去量化自选池添加" :image-size="48" />
        </div>
      </aside>

      <section class="center">
        <div class="pane quote-pane">
          <div class="quote-bar">
            <el-input v-model="form.symbol" class="sym-in" @keyup.enter="onSymbolCommit" @change="onSymbolCommit">
              <template #append>
                <el-select v-model="form.market" style="width: 86px" @change="onSymbolCommit">
                  <el-option label="US" value="US" />
                  <el-option label="HK" value="HK" />
                  <el-option label="CN" value="CN" />
                </el-select>
              </template>
            </el-input>
            <div class="q-last" :class="chgClass(quote.changeRate)">
              <strong>{{ fmt(quote.last || quote.price) }}</strong>
              <span>{{ fmtSigned(quote.change) }} {{ fmtPct(quote.changeRate) }}</span>
            </div>
            <div class="q-ohlc">
              <span>开 {{ fmt(quote.open) }}</span>
              <span>高 {{ fmt(quote.high) }}</span>
              <span>低 {{ fmt(quote.low) }}</span>
              <span>量 {{ fmtVol(quote.volume) }}</span>
            </div>
            <el-radio-group v-model="period" size="small" @change="loadKline">
              <el-radio-button v-for="p in periods" :key="p.value" :label="p.value">{{ p.label }}</el-radio-button>
            </el-radio-group>
          </div>
          <div v-show="klineItems.length" v-loading="klineLoading" ref="chartRef" class="kline" />
          <el-empty v-if="!klineLoading && !klineItems.length" :description="klineMessage || '暂无K线'" :image-size="44" />
        </div>

        <div class="mid">
          <div class="pane">
            <div class="pane-h"><span>买卖盘</span><span class="muted">{{ depthHint }}</span></div>
            <div v-if="!asks.length && !bids.length" class="empty-sm">{{ depthMeta.message || '暂无盘口' }}</div>
            <div v-else class="book">
              <div v-for="(row, i) in displayAsks" :key="'a'+i" class="book-row ask" @click="useBookPrice(row.price)">
                <i class="bar" :style="{ width: barWidth(row.volume, maxBookVol) }" />
                <span class="px">{{ fmt(row.price) }}</span>
                <span class="sz">{{ fmtVol(row.volume) }}</span>
              </div>
              <div class="book-mid" :class="chgClass(quote.changeRate)">{{ fmt(quote.last || quote.price) }}</div>
              <div v-for="(row, i) in displayBids" :key="'b'+i" class="book-row bid" @click="useBookPrice(row.price)">
                <i class="bar" :style="{ width: barWidth(row.volume, maxBookVol) }" />
                <span class="px">{{ fmt(row.price) }}</span>
                <span class="sz">{{ fmtVol(row.volume) }}</span>
              </div>
            </div>
          </div>
          <div class="pane">
            <div class="pane-h"><span>成交</span></div>
            <el-table :data="trades.slice(0, 12)" size="small" height="220" empty-text="暂无成交">
              <el-table-column width="70">
                <template #default="{ row }">{{ fmtTime(row.time) }}</template>
              </el-table-column>
              <el-table-column>
                <template #default="{ row }"><span :class="row.side === 'buy' ? 'up' : 'down'">{{ fmt(row.price) }}</span></template>
              </el-table-column>
              <el-table-column>
                <template #default="{ row }">{{ fmtVol(row.volume || row.size) }}</template>
              </el-table-column>
            </el-table>
          </div>
          <div class="pane ticket">
            <div class="pane-h"><span>快捷交易</span></div>
            <el-form label-width="56px" size="small">
              <el-form-item label="方向">
                <el-radio-group v-model="form.side">
                  <el-radio-button label="buy">买</el-radio-button>
                  <el-radio-button label="sell">卖</el-radio-button>
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
              </el-form-item>
              <div class="muted mb8">名义 ≈ {{ notional }} · 可用 {{ availableCashText }}</div>
              <el-button :type="form.side === 'buy' ? 'danger' : 'success'" style="width: 100%" :loading="submitting" :disabled="!configured" @click="submit">
                {{ form.side === 'buy' ? '买入' : '卖出' }} {{ form.symbol }}
              </el-button>
            </el-form>
          </div>
        </div>

        <div class="pane bot">
          <el-tabs v-model="bottomTab">
            <el-tab-pane label="挂单/委托" name="orders">
              <el-table :data="orders" size="small" height="150" empty-text="暂无委托">
                <el-table-column prop="symbol" label="标的" width="100" />
                <el-table-column prop="side" label="方向" width="70" />
                <el-table-column prop="status" label="状态" width="90" />
                <el-table-column prop="quantity" label="量" width="70" />
                <el-table-column prop="price" label="价" width="80" />
                <el-table-column label="操作" width="70">
                  <template #default="{ row }">
                    <el-button v-if="row.orderId" link type="danger" @click="cancel(row)">撤</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="持仓" name="pos">
              <el-table :data="positions" size="small" height="150" empty-text="暂无持仓" @row-click="fillFromPos">
                <el-table-column prop="symbol" label="代码" width="110" />
                <el-table-column prop="quantity" label="数量" width="80" />
                <el-table-column prop="costPrice" label="成本" width="90" />
                <el-table-column prop="marketValue" label="市值" />
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="资金" name="cash">
              <el-table :data="account.balances || []" size="small" height="150" empty-text="暂无">
                <el-table-column prop="currency" label="币种" width="80" />
                <el-table-column prop="netAssets" label="净资产" />
                <el-table-column prop="availableCash" label="可用" />
                <el-table-column prop="buyPower" label="购买力" />
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </div>
      </section>

      <aside class="pane side-pane">
        <el-tabs v-model="sideTab">
          <el-tab-pane label="基本信息" name="info">
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="代码">{{ form.symbol }}.{{ form.market }}</el-descriptions-item>
              <el-descriptions-item label="现价">{{ fmt(quote.last || quote.price) }}</el-descriptions-item>
              <el-descriptions-item label="昨收">{{ fmt(quote.prevClose || quote.preClose) }}</el-descriptions-item>
              <el-descriptions-item label="换手">{{ overview.turnoverRate || overview.turnover || '--' }}</el-descriptions-item>
              <el-descriptions-item label="市值">{{ overview.marketCap || overview.marketValue || '--' }}</el-descriptions-item>
              <el-descriptions-item label="PE">{{ overview.pe || overview.peTtm || '--' }}</el-descriptions-item>
              <el-descriptions-item label="PB">{{ overview.pb || '--' }}</el-descriptions-item>
            </el-descriptions>
            <div class="kv" v-if="overviewText">{{ overviewText }}</div>
          </el-tab-pane>
          <el-tab-pane label="量化指标" name="quant">
            <el-button size="small" type="primary" :loading="factorLoading" @click="loadFactor">计算因子</el-button>
            <div v-if="totalScore !== '--'" class="score">综合分 {{ totalScore }}</div>
            <el-table :data="factorRows" size="small" max-height="280" empty-text="点计算因子">
              <el-table-column prop="name" label="因子族" />
              <el-table-column prop="score" label="分" width="70" />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="AI 分析" name="ai">
            <el-button size="small" type="primary" :loading="aiLoading" @click="runAi">研判当前标的</el-button>
            <pre class="ai-box">{{ aiText || '尚未研判' }}</pre>
          </el-tab-pane>
        </el-tabs>
      </aside>
    </div>
  </div>
</template>

<script setup name="TradeDesk">
import echarts from '@/utils/echarts'
import { applyChartTheme } from '@/utils/echartsTheme'
import {
  getTradeAccount, getTradeOrders, getTradePositions, submitTradeOrder, cancelTradeOrder,
  getTradeQuoteDepth, getTradeQuoteTrades, getTradeQuoteKline
} from '@/api/trade'
import { listWatchlist, computeFactor } from '@/api/quant'
import { getBoardQuotes, aiAnalyze, getSymbolOverview, getLatestAi, pollMarketJob } from '@/api/market'

const route = useRoute()
const router = useRouter()
const { proxy } = getCurrentInstance()
const loading = ref(false)
const submitting = ref(false)
const klineLoading = ref(false)
const watchLoading = ref(false)
const factorLoading = ref(false)
const aiLoading = ref(false)
const configured = ref(true)
const account = ref({ balances: [] })
const orders = ref([])
const positions = ref([])
const watch = ref([])
const watchKw = ref('')
const period = ref('daily')
const periods = [
  { value: 'intraday', label: '分时' },
  { value: '1min', label: '1分' },
  { value: '5min', label: '5分' },
  { value: '15min', label: '15分' },
  { value: 'daily', label: '日K' },
  { value: 'weekly', label: '周K' }
]
const form = ref({ symbol: 'AAPL', market: 'US', side: 'buy', orderType: 'LO', quantity: 1, price: 100 })
applyRouteSymbol(route.query.symbol, route.query.market)
const quote = ref({})
const klineItems = ref([])
const klineMessage = ref('')
const asks = ref([])
const bids = ref([])
const trades = ref([])
const depthMeta = ref({})
const chartRef = ref(null)
const bottomTab = ref('orders')
const sideTab = ref('info')
const overview = ref({})
const factorResult = ref(null)
const aiText = ref('')
let chart = null
let liveTimer = null

const FAMILY_LABELS = {
  trend: '趋势', priceAction: '价型', momentum: '动量', breakout: '突破',
  volumeFlow: '量能', reversion: '回归', volatility: '波动', liquidity: '流动性'
}

const filteredWatch = computed(() => {
  const kw = watchKw.value.trim().toUpperCase()
  if (!kw) return watch.value
  return watch.value.filter(r => String(r.symbol || '').toUpperCase().includes(kw) || String(r.name || '').toUpperCase().includes(kw))
})
const notional = computed(() => {
  const p = form.value.orderType === 'MO' ? Number(quote.value.last || quote.value.price || 0) : Number(form.value.price || 0)
  return (p * Number(form.value.quantity || 0)).toFixed(2)
})
const availableCashText = computed(() => {
  const b = (account.value.balances || [])[0]
  return b ? `${b.availableCash || '--'} ${b.currency || ''}` : '--'
})
const displayAsks = computed(() => [...asks.value].slice(0, 8).reverse())
const displayBids = computed(() => bids.value.slice(0, 8))
const maxBookVol = computed(() => {
  const vols = [...asks.value, ...bids.value].map(r => Number(r.volume || 0)).filter(n => Number.isFinite(n))
  return vols.length ? Math.max(...vols) : 0
})
const depthHint = computed(() => (asks.value.length || bids.value.length) ? `${asks.value.length}卖/${bids.value.length}买` : '')
const factorRows = computed(() => {
  const score = factorResult.value && factorResult.value.score
  if (!score || typeof score !== 'object') return []
  return Object.keys(FAMILY_LABELS).filter(k => score[k] != null).map(k => ({ name: FAMILY_LABELS[k], score: score[k] }))
})
const totalScore = computed(() => {
  const s = factorResult.value && factorResult.value.score
  if (!s) return '--'
  return s.total != null ? s.total : '--'
})
const overviewText = computed(() => {
  const o = overview.value || {}
  return o.summary || o.description || o.message || ''
})

function isActive(row) {
  return String(row.symbol || '').toUpperCase() === String(form.value.symbol || '').toUpperCase()
    && String(row.market || '').toUpperCase() === String(form.value.market || '').toUpperCase()
}
function chgClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}
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
  router.replace({ path: '/trade/desk', query: { symbol: parsed.symbol, market: parsed.market } })
  loadSymbol()
}
function selectWatch(row) {
  form.value.symbol = row.symbol
  form.value.market = row.market || 'US'
  onSymbolCommit()
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
  quote.value = { ...quote.value, ...q, last, price: last }
  if (form.value.orderType === 'LO' && (form.value.price == null || form.value.price === 100)) {
    const n = Number(last)
    if (Number.isFinite(n) && n > 0) form.value.price = n
  }
}
async function loadWatch() {
  watchLoading.value = true
  try {
    const [w, q] = await Promise.all([
      listWatchlist({ pageNum: 1, pageSize: 200 }),
      getBoardQuotes({}).catch(() => ({ data: {} }))
    ])
    const rows = w.rows || w.data || []
    const quotes = ((q.data || {}).rows || (q.data || {}).quotes || [])
    const map = {}
    quotes.forEach(it => {
      map[`${String(it.symbol || '').toUpperCase()}|${String(it.market || '').toUpperCase()}`] = it
    })
    watch.value = rows.map(r => {
      const hit = map[`${String(r.symbol || '').toUpperCase()}|${String(r.market || '').toUpperCase()}`] || {}
      return {
        ...r,
        name: r.name || hit.name,
        price: hit.price || hit.last,
        changeRate: hit.changeRate != null ? hit.changeRate : hit.change
      }
    })
  } finally {
    watchLoading.value = false
  }
}
async function loadKline() {
  if (!form.value.symbol) return
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
    klineMessage.value = data.message || ''
    if (data.configured === false) configured.value = false
    if (data.quote) applyQuote(data.quote)
    await nextTick()
    renderChart()
  } catch {
    klineItems.value = []
    klineMessage.value = 'K线加载失败'
    renderChart()
  } finally {
    klineLoading.value = false
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
    if (data.last) applyQuote({ last: data.last })
  } catch {
    asks.value = []
    bids.value = []
  }
}
async function loadTrades() {
  try {
    const res = await getTradeQuoteTrades({ symbol: form.value.symbol, market: form.value.market, count: 40 })
    trades.value = (res.data || {}).trades || []
  } catch {
    trades.value = []
  }
}
async function loadOverview() {
  try {
    const res = await getSymbolOverview(form.value.symbol, { market: form.value.market })
    overview.value = res.data || {}
  } catch {
    overview.value = {}
  }
}
async function loadFactor() {
  factorLoading.value = true
  try {
    const res = await computeFactor({ symbol: form.value.symbol, market: form.value.market, profile: 'balanced' })
    factorResult.value = res.data || null
  } catch {
    factorResult.value = null
  } finally {
    factorLoading.value = false
  }
}
async function runAi() {
  aiLoading.value = true
  try {
    const res = await aiAnalyze({ symbol: form.value.symbol, market: form.value.market, days: 90 })
    const d = res.data || {}
    if (d.accepted || d.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队')
      if (d.jobId) {
        const ticket = await pollMarketJob(d.jobId)
        if (ticket.status === 'failed') {
          aiText.value = ticket.error || '研判失败'
          return
        }
      }
      const latest = await getLatestAi(form.value.symbol, { market: form.value.market })
      const data = latest.data || {}
      aiText.value = data.content || data.analysis || data.summary || data.message || JSON.stringify(data, null, 2)
      return
    }
    aiText.value = d.content || d.analysis || d.summary || d.message || JSON.stringify(d, null, 2)
  } catch (e) {
    aiText.value = e.message || '研判失败'
  } finally {
    aiLoading.value = false
  }
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
    ? [{ name: '分时', type: 'line', data: items.map(i => i.close), smooth: true, showSymbol: false, lineStyle: { width: 2, color: up }, areaStyle: { opacity: 0.1, color: up } }]
    : [{ name: 'K线', type: 'candlestick', data: items.map(i => [i.open, i.close, i.low, i.high]), itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down } }]
  series.push({
    name: '成交量',
    type: 'bar',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: items.map(i => ({ value: i.volume, itemStyle: { color: Number(i.close) >= Number(i.open) ? up : down } }))
  })
  chart.setOption(applyChartTheme({
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [{ left: 48, right: 12, top: 16, height: '58%' }, { left: 48, right: 12, top: '78%', height: '14%' }],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: !isLine, axisLine: { onZero: false } },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: !isLine, axisLabel: { show: false }, axisTick: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { type: 'dashed' } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: isLine ? 0 : 55, end: 100 }],
    series
  }), true)
}
async function loadOrders() {
  const o = await getTradeOrders('today')
  orders.value = (o.data && o.data.orders) || []
  if (o.data && o.data.configured === false) configured.value = false
}
async function loadSymbol() {
  factorResult.value = null
  aiText.value = ''
  await Promise.all([loadKline(), loadDepth(), loadTrades(), loadOverview()])
}
async function refreshAll() {
  loading.value = true
  try {
    const [a, p] = await Promise.all([getTradeAccount(), getTradePositions(), loadOrders(), loadWatch(), loadSymbol()])
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
  await loadOrders()
}
function stopLive() {
  if (liveTimer) {
    clearInterval(liveTimer)
    liveTimer = null
  }
}
function tickLive() {
  loadKline()
  if (String(form.value.market).toUpperCase() !== 'CN' && configured.value) {
    loadDepth()
    loadTrades()
  }
}
function startLive() {
  stopLive()
  if (document.hidden) return
  liveTimer = setInterval(tickLive, 20000)
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
function handleResize() { chart && chart.resize() }
onMounted(() => {
  refreshAll()
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('visibilitychange', handleVisibility)
  stopLive()
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.desk-page { height: calc(100vh - 92px); display: flex; flex-direction: column; min-height: 640px; }
.desk-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; }
.desk-top h2 { margin: 0 0 2px; font-size: 18px; }
.desk-top p { margin: 0; color: var(--text-muted); font-size: 12px; }
.acts { display: flex; gap: 8px; align-items: center; }
.desk-grid { flex: 1; min-height: 0; display: grid; grid-template-columns: 240px minmax(0, 1fr) 300px; gap: 8px; }
.pane { background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; padding: 8px; min-height: 0; overflow: hidden; }
.pane-h { display: flex; justify-content: space-between; align-items: center; font-weight: 600; margin-bottom: 6px; font-size: 13px; }
.watch-pane, .side-pane { display: flex; flex-direction: column; }
.watch-list { flex: 1; overflow: auto; }
.watch-row { display: flex; justify-content: space-between; padding: 8px 6px; border-radius: 6px; cursor: pointer; }
.watch-row.active, .watch-row:hover { background: var(--el-fill-color-light); }
.sym { font-weight: 700; }
.nm { font-size: 11px; color: var(--el-text-color-secondary); }
.px { text-align: right; font-variant-numeric: tabular-nums; }
.chg { font-size: 11px; }
.center { display: grid; grid-template-rows: minmax(220px, 1.3fr) 250px 190px; gap: 8px; min-width: 0; }
.quote-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px; }
.sym-in { width: 200px; }
.q-last { display: flex; flex-direction: column; }
.q-last strong { font-size: 22px; line-height: 1; }
.q-ohlc { display: flex; gap: 10px; font-size: 12px; color: var(--el-text-color-secondary); }
.kline { height: calc(100% - 48px); min-height: 180px; }
.mid { display: grid; grid-template-columns: 1fr 1fr 220px; gap: 8px; min-height: 0; }
.book { font-size: 12px; font-variant-numeric: tabular-nums; }
.book-row { position: relative; display: flex; justify-content: space-between; padding: 2px 4px; cursor: pointer; }
.book-row .bar { position: absolute; inset: 0 auto 0 0; opacity: .15; }
.ask .bar { background: #67c23a; }
.bid .bar { background: #f56c6c; }
.book-mid { text-align: center; font-weight: 700; padding: 4px 0; }
.ticket .el-form-item { margin-bottom: 8px; }
.bot { padding-bottom: 0; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.mb8 { margin-bottom: 8px; }
.empty-sm { color: var(--el-text-color-secondary); font-size: 12px; padding: 20px 0; text-align: center; }
.up { color: #f56c6c; }
.down { color: #67c23a; }
.score { font-size: 20px; font-weight: 700; margin: 8px 0; }
.ai-box { white-space: pre-wrap; font-size: 12px; line-height: 1.5; max-height: 420px; overflow: auto; margin-top: 8px; }
.kv { margin-top: 8px; font-size: 12px; color: var(--el-text-color-regular); white-space: pre-wrap; }
@media (max-width: 1100px) {
  .desk-grid { grid-template-columns: 1fr; }
  .center { grid-template-rows: 280px auto 200px; }
  .mid { grid-template-columns: 1fr; }
}
</style>
