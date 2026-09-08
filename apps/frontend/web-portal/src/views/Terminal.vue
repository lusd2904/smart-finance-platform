<template>
  <div class="pro-terminal-page" :class="{ 'is-fullscreen': isFullscreen }">
    <div v-if="usingStub && showStubBanner()" class="stub-banner">演示</div>

    <div class="terminal-topbar glass-panel">
      <div class="topbar-indices-wrap">
        <div
          v-for="idx in indices"
          :key="idx.symbol"
          class="index-card-chip"
          :class="idx.changeRate >= 0 ? 'up' : 'down'"
        >
          <span class="mkt-session-badge">{{ idx.sessionStatus?.sessionName || idx.market }}</span>
          <span class="idx-name">{{ idx.name }}</span>
          <span class="idx-price">{{ fmtPx(idx.price) }}</span>
          <span class="idx-change">{{ fmtSigned(idx.changeRate) }}%</span>
        </div>
      </div>
      <div class="topbar-right-controls">
        <el-autocomplete
          v-model="searchKeyword"
          :fetch-suggestions="querySearch"
          value-key="symbol"
          placeholder="代码 / 名称"
          size="small"
          class="top-search-box"
          :prefix-icon="Search"
          clearable
          @select="handleSearchSelect"
        />
        <div class="cash-stat-capsule">
          <span>可用资金</span>
          <strong>{{ cashCurrency }} {{ Number(accountCash || 0).toLocaleString('en-US', { minimumFractionDigits: 2 }) }}</strong>
        </div>
        <div class="auto-trade-switch">
          <span>量化</span>
          <el-switch v-model="autoTradeEnabled" size="small" :disabled="!autoTradeConfigured" @change="onToggleAutoTrade" />
        </div>
        <span class="live-flag" :class="liveMode ? 'on' : 'off'">{{ liveMode ? 'LIVE' : '无数据' }}</span>
        <el-button circle size="small" :icon="Refresh" @click="refreshLive" />
        <el-button circle size="small" :icon="FullScreen" @click="isFullscreen = !isFullscreen" />
      </div>
    </div>

    <div class="terminal-main-grid">
      <aside class="panel-card left-pane glass-panel">
        <div class="panel-head">
          <div class="head-left">
            <el-icon class="star-icon"><StarFilled /></el-icon>
            <span>自选清单</span>
            <span class="count-badge">{{ filteredStocks.length }}</span>
          </div>
          <el-dropdown trigger="click" @command="currentGroup = $event">
            <span class="group-select-btn">{{ currentGroup }} <el-icon><ArrowDown /></el-icon></span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="g in watchGroupNames" :key="g" :command="g">{{ g === '全部' ? '全部自选' : g }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="watchlist-toolbar">
          <el-input v-model="watchFilterKw" placeholder="过滤代码/名称..." size="small" clearable :prefix-icon="Search" />
          <div class="sort-actions-bar">
            <span class="sort-tab" :class="{ active: sortField === 'changeRate' }" @click="toggleSort('changeRate')">涨跌幅</span>
            <span class="sort-tab" :class="{ active: sortField === 'price' }" @click="toggleSort('price')">现价</span>
            <span class="sort-tab" :class="{ active: sortField === 'turnover' }" @click="toggleSort('turnover')">成交额</span>
          </div>
        </div>
        <div class="watchlist-body">
          <el-empty v-if="!sortedWatchStocks.length" description="暂无自选" :image-size="56" />
          <div
            v-for="item in sortedWatchStocks"
            :key="item.symbol + '.' + item.market"
            class="stock-row-card"
            :class="{ active: activeSymbol === item.symbol }"
            @click="selectStock(item)"
          >
            <div class="stock-info">
              <div class="sym-line">
                <span class="stock-code">{{ item.symbol }}</span>
                <span class="market-badge">{{ item.market }}</span>
              </div>
              <div class="stock-name">{{ item.name }}</div>
            </div>
            <svg viewBox="0 0 60 22" class="spark-svg">
              <path :d="renderSparklinePath(item.sparkline)" fill="none" :stroke="item.changeRate >= 0 ? 'var(--stat-up)' : 'var(--stat-down)'" stroke-width="1.6" />
            </svg>
            <div class="price-info">
              <div class="price-val">{{ fmtPx(item.price) }}</div>
              <div class="change-pill" :class="item.changeRate >= 0 ? 'up' : 'down'">{{ fmtSigned(item.changeRate) }}%</div>
            </div>
          </div>
        </div>
        <div class="watchlist-footer">
          <div class="footer-stat-line">
            <span>自选组合今日走势</span>
            <strong :class="watchStats.avg >= 0 ? 'up' : 'down'">{{ fmtSigned(watchStats.avg) }}%</strong>
          </div>
          <div class="stat-sub-info">
            <span class="up">上涨 {{ watchStats.up }}</span>
            <span>平盘 {{ watchStats.flat }}</span>
            <span class="down">下跌 {{ watchStats.down }}</span>
          </div>
        </div>
      </aside>

      <section class="panel-card center-pane glass-panel">
        <div class="ticker-board-card">
          <div class="ticker-top-row">
            <div>
              <div class="name-line">
                <span class="big-symbol">{{ activeStock.symbol }}</span>
                <span class="full-name">{{ activeStock.name }}</span>
                <el-tag size="small" type="warning">AI 研判 {{ activeStock.aiScore != null ? activeStock.aiScore + '分' : '--' }}</el-tag>
              </div>
              <div class="muted">市场: {{ activeStock.market }} ({{ activeStock.currency }}) · {{ activeSession }}</div>
            </div>
            <div class="ticker-price-block" :class="activeStock.changeRate >= 0 ? 'up' : 'down'">
              <div class="main-price-num">{{ fmtNum(activeStock.price, 3) }} <small>{{ activeStock.currency }}</small></div>
              <div>{{ fmtSigned(activeStock.change, 3) }} ({{ fmtSigned(activeStock.changeRate) }}%)</div>
            </div>
          </div>
          <div class="quote-metrics-grid">
            <div class="q-cell"><span>今开</span><b>{{ fmtNum(activeStock.open, 3) }}</b></div>
            <div class="q-cell"><span>最高</span><b class="up">{{ fmtNum(activeStock.high, 3) }}</b></div>
            <div class="q-cell"><span>最低</span><b class="down">{{ fmtNum(activeStock.low, 3) }}</b></div>
            <div class="q-cell"><span>昨收</span><b>{{ fmtNum(activeStock.prevClose, 3) }}</b></div>
            <div class="q-cell"><span>成交量</span><b>{{ formatVolume(activeStock.volume) }}</b></div>
            <div class="q-cell"><span>成交额</span><b>{{ formatTurnover(activeStock.turnover) }}</b></div>
            <div class="q-cell"><span>换手率</span><b>{{ activeStock.turnoverRate || '--' }}</b></div>
            <div class="q-cell"><span>振幅</span><b>{{ activeStock.amplitude || '--' }}</b></div>
            <div class="q-cell"><span>量比</span><b>{{ activeStock.volumeRatio || '--' }}</b></div>
            <div class="q-cell"><span>市盈率(TTM)</span><b>{{ activeStock.peTTM || '--' }}</b></div>
            <div class="q-cell"><span>市净率 PB</span><b>{{ activeStock.pb || '--' }}</b></div>
            <div class="q-cell"><span>总市值</span><b>{{ activeStock.marketCap || '--' }}</b></div>
          </div>
        </div>

        <div class="chart-action-bar">
          <div class="period-button-group">
            <button v-for="p in periodOptions" :key="p.value" class="period-toggle-btn" :class="{ active: currentPeriod === p.value }" @click="setPeriod(p.value)">{{ p.label }}</button>
          </div>
          <div class="indicator-group-wrap">
            <span>主图:</span>
            <el-checkbox-group v-model="mainIndicators" size="small" @change="renderChart">
              <el-checkbox-button value="MA">MA均线</el-checkbox-button>
              <el-checkbox-button value="BOLL">BOLL</el-checkbox-button>
            </el-checkbox-group>
            <span>副图:</span>
            <el-radio-group v-model="subIndicator" size="small" @change="renderChart">
              <el-radio-button value="VOL">VOL量</el-radio-button>
              <el-radio-button value="MACD">MACD</el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <div class="chart-canvas-container">
          <div ref="chartRef" class="echarts-inner-dom"></div>
        </div>
        <el-tabs v-model="activeBottomTab" class="sub-analysis-tabs">
          <el-tab-pane name="ai" label="AI 研判">
            <div class="tab-pane-ai">
              <strong>{{ activeStock.aiVerdict || '暂无结论' }}</strong>
              <p>{{ activeStock.aiSummary || '暂无研判' }}</p>
              <div class="factor-chips-row">
                <span v-for="f in activeStock.factors || []" :key="f.name" class="factor-score-chip">{{ f.name }} {{ f.score }}分</span>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane name="news" label="标的快讯与舆情">
            <div v-if="!(activeStock.news || []).length" class="muted">暂无快讯</div>
            <div v-for="item in activeStock.news || []" :key="item.id" class="news-item-line">
              <el-tag size="small" :type="item.sentiment === 'bull' ? 'danger' : item.sentiment === 'bear' ? 'success' : 'info'">
                {{ item.sentiment === 'bull' ? '利多' : item.sentiment === 'bear' ? '利空' : '中性' }}
              </el-tag>
              <span>{{ item.title }}</span>
              <span class="muted">{{ item.source }} {{ item.time }}</span>
            </div>
          </el-tab-pane>
          <el-tab-pane name="flow" label="资金大单博弈">
            <div v-if="!activeStock.capitalFlow" class="muted">暂无资金</div>
            <div v-else class="flow-cards-grid">
              <div>超大单净流入 <b class="up">{{ activeStock.capitalFlow.superIn - activeStock.capitalFlow.superOut }} 万</b></div>
              <div>大单净流入 <b>{{ activeStock.capitalFlow.largeIn - activeStock.capitalFlow.largeOut }} 万</b></div>
              <div>当日主力净额 <b class="up">{{ activeStock.capitalFlow.netInflow }} 万</b></div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </section>

      <aside class="right-pane">
        <div class="depth-stream-card glass-panel">
          <el-tabs v-model="rightTopTab" class="tight-tabs">
            <el-tab-pane label="基本信息" name="info">
              <div class="info-hero-price-box" :class="activeStock.changeRate >= 0 ? 'up' : 'down'">
                <span class="price-main-num">{{ fmtPx(activeStock.price, 3) }}</span>
                <span>{{ fmtSigned(activeStock.changeRate) }}%</span>
              </div>
              <div class="info-detailed-metrics-grid">
                <div class="m-row"><span>最高</span><b class="up">{{ fmtPx(activeStock.high, 3) }}</b><span>最低</span><b class="down">{{ fmtPx(activeStock.low, 3) }}</b></div>
                <div class="m-row"><span>今开</span><b>{{ fmtPx(activeStock.open, 3) }}</b><span>昨收</span><b>{{ fmtPx(activeStock.prevClose, 3) }}</b></div>
                <div class="m-row"><span>成交量</span><b>{{ formatVolume(activeStock.volume) }}</b><span>成交额</span><b>{{ formatTurnover(activeStock.turnover) }}</b></div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="盘口" name="depth">
              <div class="orderbook-wrap">
                <div v-for="ask in (activeStock.asks || [])" :key="'a'+ask.level" class="book-row" @click="fillOrderPrice(ask.price)">
                  <span class="down">{{ fmtPx(ask.price) }}</span>
                  <span>{{ ask.volume }}</span>
                </div>
                <div class="book-mid">{{ fmtPx(activeStock.price, 3) }}</div>
                <div v-for="bid in (activeStock.bids || [])" :key="'b'+bid.level" class="book-row" @click="fillOrderPrice(bid.price)">
                  <span class="up">{{ fmtPx(bid.price) }}</span>
                  <span>{{ bid.volume }}</span>
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="逐笔" name="trades">
              <div v-for="(t, idx) in (activeStock.trades || [])" :key="idx" class="stream-item-row">
                <span>{{ t.time }}</span>
                <span :class="t.side === 'buy' ? 'up' : 'down'">{{ fmtPx(t.price) }}</span>
                <span>{{ t.volume }}</span>
                <span>{{ t.side === 'buy' ? '买盘' : '卖盘' }}</span>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <div class="range-metric-card glass-panel">
          <span>52周价格区间 · 当前 {{ weekPos }}% 分位</span>
          <div class="range-track">
            <span>{{ fmtPx(activeStock.low52) }}</span>
            <div class="track-bg"><i :style="{ left: weekPos + '%' }"></i></div>
            <span>{{ fmtPx(activeStock.high52) }}</span>
          </div>
        </div>

        <div class="quick-trade-card glass-panel">
          <div class="trade-side-switcher">
            <button class="side-btn buy-btn" :class="{ active: tradeForm.side === 'BUY' }" @click="tradeForm.side = 'BUY'">买入 {{ activeStock.symbol }}</button>
            <button class="side-btn sell-btn" :class="{ active: tradeForm.side === 'SELL' }" @click="tradeForm.side = 'SELL'">卖出 {{ activeStock.symbol }}</button>
          </div>
          <el-radio-group v-model="tradeForm.type" size="small">
            <el-radio-button value="LIMIT">限价单 LO</el-radio-button>
            <el-radio-button value="MARKET">市价单 MO</el-radio-button>
          </el-radio-group>
          <el-input-number v-if="tradeForm.type === 'LIMIT'" v-model="tradeForm.price" :precision="2" :step="0.05" size="small" style="width:100%" />
          <el-input-number v-model="tradeForm.quantity" :min="1" :step="10" size="small" style="width:100%" />
          <div class="ratio-pill-row">
            <button v-for="r in [0.25, 0.5, 0.75, 1]" :key="r" class="r-pill" @click="applyRatio(r)">{{ r === 1 ? '全仓' : (r * 100) + '%' }}</button>
          </div>
          <div class="muted">名义金额 {{ calcNotional().toLocaleString('en-US', { minimumFractionDigits: 2 }) }}</div>
          <el-button class="do-order-btn" :class="tradeForm.side === 'BUY' ? 'btn-order-buy' : 'btn-order-sell'" :loading="orderSubmitting" @click="submitOrder">
            极速{{ tradeForm.side === 'BUY' ? '买入' : '卖出' }} {{ activeStock.symbol }}
          </el-button>
        </div>

        <div class="bottom-orders-card glass-panel">
          <el-tabs v-model="bottomRightTab">
            <el-tab-pane :label="`当日委托 (${orders.length})`" name="orders">
              <div v-for="o in orders" :key="o.id" class="order-item-card">
                <span :class="o.side === 'BUY' ? 'up' : 'down'">{{ o.side === 'BUY' ? '买' : '卖' }}</span>
                <span>{{ o.symbol }} {{ o.quantity }}股 @ {{ o.price }}</span>
                <el-tag size="small">{{ o.status }}</el-tag>
              </div>
              <div v-if="!orders.length" class="muted">暂无当日委托</div>
            </el-tab-pane>
            <el-tab-pane :label="`持仓 (${positions.length})`" name="pos">
              <div v-for="p in positions" :key="p.symbol" class="order-item-card" @click="selectStockBySymbol(p.symbol)">
                <span>{{ p.symbol }}</span>
                <span>{{ p.quantity }} 股</span>
                <b :class="p.pnl >= 0 ? 'up' : 'down'">{{ fmtSigned(p.pnlRate) }}%</b>
              </div>
              <div v-if="!positions.length" class="muted">暂无持仓</div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, FullScreen, Refresh, Search, StarFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getKline, getMarketIndexQuotes, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import { getAutoTradeStatus, getTradeAccount, getTradeOrders, getTradePositions, getTradeQuoteDepth, getTradeQuoteSnapshot, getTradeQuoteTrades, saveAutoTradeSettings, submitTradeOrder } from '@/api/trade'
import { useUserStore } from '@/store/user'
import { fmtNum, fmtPx, fmtSigned, formatTurnover, formatVolume, renderSparklinePath } from '@/utils/format'
import { showStubBanner, stubAccount, stubIndices, stubKline, stubOrders, stubPositions, stubWatchlist, useStubs } from '@/utils/stubs'

const route = useRoute()
const userStore = useUserStore()
const usingStub = ref(false)
const liveMode = ref(false)
const isFullscreen = ref(false)
const searchKeyword = ref('')
const watchFilterKw = ref('')
const currentGroup = ref('全部')
const sortField = ref('changeRate')
const sortOrder = ref('desc')
const indices = ref([])
const watchStocks = ref([])
const activeSymbol = ref('')
const bars = ref([])
const accountCash = ref(0)
const cashCurrency = ref('HKD')
const autoTradeEnabled = ref(false)
const autoTradeConfigured = ref(false)
const orderSubmitting = ref(false)
const orders = ref([])
const positions = ref([])
const currentPeriod = ref('day')
const mainIndicators = ref(['MA'])
const subIndicator = ref('VOL')
const activeBottomTab = ref('ai')
const rightTopTab = ref('info')
const bottomRightTab = ref('orders')
const chartRef = ref(null)
let chart
const periodOptions = [
  { label: '分时', value: 'min1' },
  { label: '日K', value: 'day' },
  { label: '周K', value: 'week' },
  { label: '月K', value: 'month' }
]
const tradeForm = reactive({ side: 'BUY', type: 'LIMIT', price: 0, quantity: 100 })

const activeStock = computed(() => watchStocks.value.find((s) => s.symbol === activeSymbol.value) || watchStocks.value[0] || { symbol: '--', name: '未选择标的', market: '--', currency: '--' })
const activeSession = computed(() => activeStock.value.quoteTime || '行情待同步')
const watchGroupNames = computed(() => {
  const set = new Set(['全部'])
  watchStocks.value.forEach((s) => (s.groups || []).forEach((g) => set.add(g)))
  return Array.from(set)
})
const filteredStocks = computed(() => {
  return watchStocks.value.filter((s) => {
    const groupOk = currentGroup.value === '全部' || (s.groups || []).includes(currentGroup.value)
    const kw = watchFilterKw.value.trim().toLowerCase()
    const textOk = !kw || `${s.symbol} ${s.name}`.toLowerCase().includes(kw)
    return groupOk && textOk
  })
})
const sortedWatchStocks = computed(() => {
  const list = [...filteredStocks.value]
  list.sort((a, b) => {
    const av = Number(a[sortField.value]) || 0
    const bv = Number(b[sortField.value]) || 0
    return sortOrder.value === 'desc' ? bv - av : av - bv
  })
  return list
})
const watchStats = computed(() => {
  const list = filteredStocks.value
  const up = list.filter((s) => s.changeRate > 0).length
  const down = list.filter((s) => s.changeRate < 0).length
  const flat = list.length - up - down
  const avg = list.length ? list.reduce((sum, s) => sum + (Number(s.changeRate) || 0), 0) / list.length : 0
  return { up, down, flat, avg }
})
const weekPos = computed(() => {
  const low = Number(activeStock.value.low52)
  const high = Number(activeStock.value.high52)
  const px = Number(activeStock.value.price)
  if (![low, high, px].every(Number.isFinite) || high <= low) return 50
  return Math.min(100, Math.max(0, Math.round(((px - low) / (high - low)) * 100)))
})

function toggleSort(field) {
  if (sortField.value === field) sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  else {
    sortField.value = field
    sortOrder.value = 'desc'
  }
}

function selectStock(item) {
  activeSymbol.value = item.symbol
  tradeForm.price = Number(item.price) || 0
  loadSymbolExtras(item)
}

function selectStockBySymbol(sym) {
  const target = watchStocks.value.find((s) => s.symbol === sym)
  if (target) selectStock(target)
}

function fillOrderPrice(p) {
  tradeForm.price = Number(p) || 0
}

function applyRatio(ratio) {
  const px = tradeForm.type === 'LIMIT' ? tradeForm.price : activeStock.value.price
  if (!px || !accountCash.value) return
  tradeForm.quantity = Math.max(1, Math.floor((accountCash.value * ratio) / px))
}

function calcNotional() {
  const px = tradeForm.type === 'LIMIT' ? tradeForm.price : Number(activeStock.value.price) || 0
  return (Number(tradeForm.quantity) || 0) * px
}

function querySearch(queryString, cb) {
  const q = (queryString || '').toLowerCase()
  const local = watchStocks.value.filter((s) => `${s.symbol} ${s.name}`.toLowerCase().includes(q))
  cb(local.slice(0, 12))
}

function handleSearchSelect(item) {
  selectStockBySymbol(item.symbol)
}

function applyQuerySymbol() {
  const symbol = String(route.query.symbol || '').trim()
  if (!symbol) return
  const hit = watchStocks.value.find((s) => String(s.symbol).toUpperCase() === symbol.toUpperCase())
  if (hit) {
    selectStock(hit)
    return
  }
  activeSymbol.value = symbol
}

function applyStubTerminal() {
  usingStub.value = true
  liveMode.value = false
  indices.value = stubIndices()
  watchStocks.value = stubWatchlist()
  activeSymbol.value = watchStocks.value[0].symbol
  bars.value = stubKline(watchStocks.value[0].price)
  const acc = stubAccount()
  accountCash.value = acc.availableCash
  cashCurrency.value = acc.currency
  orders.value = stubOrders()
  positions.value = stubPositions()
  tradeForm.price = watchStocks.value[0].price
  nextTick(renderChart)
}

function unwrap(res) {
  return res?.data ?? res ?? {}
}

async function loadLive() {
  if (useStubs() || userStore.usingStub) {
    applyStubTerminal()
    applyQuerySymbol()
    return
  }
  try {
    const [idxRes, watchRes, accRes, orderRes, posRes, autoRes] = await Promise.allSettled([
      getMarketIndexQuotes(),
      getMarketWatchlistOverview().catch(() => listMarketWatchlist()),
      getTradeAccount(),
      getTradeOrders('today'),
      getTradePositions(),
      getAutoTradeStatus()
    ])
    let any = false
    if (idxRes.status === 'fulfilled') {
      const items = unwrap(idxRes.value).items || unwrap(idxRes.value).list || unwrap(idxRes.value)
      if (Array.isArray(items) && items.length) {
        indices.value = items
        any = true
      }
    }
    if (watchRes.status === 'fulfilled') {
      const raw = unwrap(watchRes.value)
      const items = raw.items || raw.list || raw.watchlist || []
      if (items.length) {
        watchStocks.value = items.map((r) => ({
          symbol: r.symbol,
          name: r.name,
          market: r.market,
          currency: r.currency,
          price: Number(r.price || r.last || 0),
          change: Number(r.change || 0),
          changeRate: Number(r.changeRate || r.chgPct || 0),
          open: Number(r.open || 0),
          high: Number(r.high || 0),
          low: Number(r.low || 0),
          prevClose: Number(r.prevClose || r.prev_close || 0),
          volume: Number(r.volume || 0),
          turnover: Number(r.turnover || 0),
          groups: r.groups || r.groupNames || ['全部'],
          sparkline: r.sparkline || [],
          ...r
        }))
        any = true
      }
    }
    if (accRes.status === 'fulfilled') {
      const acc = unwrap(accRes.value)
      accountCash.value = Number(acc.availableCash || acc.cash || 0)
      cashCurrency.value = acc.currency || 'HKD'
      if (acc.availableCash != null) any = true
    }
    if (orderRes.status === 'fulfilled') {
      const raw = unwrap(orderRes.value)
      orders.value = raw.items || raw.list || []
    }
    if (posRes.status === 'fulfilled') {
      const raw = unwrap(posRes.value)
      positions.value = raw.items || raw.list || []
    }
    if (autoRes.status === 'fulfilled') {
      const auto = unwrap(autoRes.value)
      autoTradeConfigured.value = Boolean(auto.configured ?? auto.enabled != null)
      autoTradeEnabled.value = Boolean(auto.enabled)
    }
    if (!any) {
      applyStubTerminal()
      applyQuerySymbol()
      return
    }
    usingStub.value = false
    liveMode.value = true
    applyQuerySymbol()
    if (!activeSymbol.value && watchStocks.value[0]) selectStock(watchStocks.value[0])
    else if (activeSymbol.value) await loadSymbolExtras(activeStock.value)
  } catch {
    applyStubTerminal()
    applyQuerySymbol()
  }
}

async function loadSymbolExtras(item) {
  if (!item?.symbol || usingStub.value || useStubs() || userStore.usingStub) {
    bars.value = stubKline(item?.price || 100)
    nextTick(renderChart)
    return
  }
  try {
    const [klineRes, depthRes, tradesRes, snapRes] = await Promise.allSettled([
      getKline({ symbol: item.symbol, market: item.market, period: currentPeriod.value }),
      getTradeQuoteDepth({ symbol: item.symbol, market: item.market }),
      getTradeQuoteTrades({ symbol: item.symbol, market: item.market }),
      getTradeQuoteSnapshot({ symbol: item.symbol, market: item.market })
    ])
    if (klineRes.status === 'fulfilled') {
      const raw = unwrap(klineRes.value)
      bars.value = raw.items || raw.list || raw.klines || []
    }
    if (!bars.value.length) bars.value = stubKline(item.price)
    const idx = watchStocks.value.findIndex((s) => s.symbol === item.symbol)
    if (idx >= 0) {
      const next = { ...watchStocks.value[idx] }
      if (depthRes.status === 'fulfilled') {
        const d = unwrap(depthRes.value)
        next.asks = d.asks || next.asks
        next.bids = d.bids || next.bids
      }
      if (tradesRes.status === 'fulfilled') {
        const d = unwrap(tradesRes.value)
        next.trades = d.items || d.list || next.trades
      }
      if (snapRes.status === 'fulfilled') {
        Object.assign(next, unwrap(snapRes.value))
      }
      watchStocks.value.splice(idx, 1, next)
    }
  } catch {
    bars.value = stubKline(item.price)
  }
  nextTick(renderChart)
}

function setPeriod(p) {
  currentPeriod.value = p
  loadSymbolExtras(activeStock.value)
}

function quotePalette() {
  const styles = getComputedStyle(document.documentElement)
  return {
    up: styles.getPropertyValue('--stat-up').trim() || '#ff0055',
    down: styles.getPropertyValue('--stat-down').trim() || '#39ff14'
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const dark = document.documentElement.dataset.theme !== 'glass-light'
  const { up, down } = quotePalette()
  const data = bars.value.map((b) => [b.open ?? b[1], b.close ?? b[2], b.low ?? b[3], b.high ?? b[4]])
  const cats = bars.value.map((b, i) => b.time || b.date || b.t || i)
  const closes = bars.value.map((b) => Number(b.close ?? b[2]) || 0)
  const ma = closes.map((_, i) => {
    if (i < 4) return null
    return (closes.slice(i - 4, i + 1).reduce((a, c) => a + c, 0) / 5).toFixed(2)
  })
  chart.setOption({
    backgroundColor: 'transparent',
    animation: false,
    grid: [{ left: 48, right: 16, top: 16, height: '58%' }, { left: 48, right: 16, top: '76%', height: '16%' }],
    xAxis: [
      { type: 'category', data: cats, axisLine: { lineStyle: { color: '#64748b' } } },
      { type: 'category', data: cats, gridIndex: 1, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' } } },
      { gridIndex: 1, splitLine: { show: false } }
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
    series: [
      { type: 'candlestick', data, itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down } },
      ...(mainIndicators.value.includes('MA') ? [{ type: 'line', data: ma, symbol: 'none', lineStyle: { width: 1, color: '#00f0ff' } }] : []),
      { type: 'bar', data: bars.value.map((b) => b.volume || 0), xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: '#64748b' } }
    ]
  }, true)
}

async function submitOrder() {
  orderSubmitting.value = true
  try {
    if (!usingStub.value && !userStore.usingStub) {
      await submitTradeOrder({
        symbol: activeStock.value.symbol,
        market: activeStock.value.market,
        side: tradeForm.side,
        type: tradeForm.type,
        price: tradeForm.price,
        quantity: tradeForm.quantity
      })
    } else {
      orders.value.unshift({
        id: `stub-${Date.now()}`,
        symbol: activeStock.value.symbol,
        side: tradeForm.side,
        quantity: tradeForm.quantity,
        price: tradeForm.price,
        status: '已提交',
        open: true
      })
    }
    ElMessage.success('下单请求已提交')
  } catch (e) {
    ElMessage.error(e?.message || '下单失败')
  } finally {
    orderSubmitting.value = false
  }
}

async function onToggleAutoTrade(val) {
  try {
    await saveAutoTradeSettings({ enabled: val })
  } catch {
    autoTradeEnabled.value = !val
    ElMessage.warning('自动交易开关接口不可用')
  }
}

async function refreshLive() {
  await loadLive()
}

watch(
  () => [route.query.symbol, route.query.market],
  () => applyQuerySymbol()
)

onMounted(async () => {
  await loadLive()
  window.addEventListener('resize', () => chart && chart.resize())
})

onBeforeUnmount(() => {
  chart && chart.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.pro-terminal-page {
  display: grid;
  gap: 8px;
  min-height: calc(100vh - 96px);
}

.pro-terminal-page.is-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 80;
  padding: 10px;
  background: var(--page-bg-color);
}

.terminal-topbar {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  flex-wrap: wrap;
}

.topbar-indices-wrap,
.topbar-right-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.index-card-chip,
.cash-stat-capsule,
.auto-trade-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 8px;
  background: var(--surface-soft);
  font-size: 12px;
}

.live-flag {
  font-size: 11px;
  font-weight: 700;
  &.on { color: var(--success); }
  &.off { color: var(--text-muted); }
}

.terminal-main-grid {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
  gap: 8px;
  min-height: 0;
}

.panel-card,
.depth-stream-card,
.range-metric-card,
.quick-trade-card,
.bottom-orders-card {
  padding: 8px 10px;
}

.left-pane,
.center-pane,
.right-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.panel-head,
.ticker-top-row,
.chart-action-bar,
.footer-stat-line,
.stat-sub-info,
.m-row,
.book-row,
.stream-item-row,
.order-item-card,
.news-item-line,
.flow-cards-grid {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.watchlist-body {
  flex: 1;
  overflow: auto;
  max-height: 52vh;
}

.stock-row-card {
  display: grid;
  grid-template-columns: 1fr 64px auto;
  gap: 8px;
  align-items: center;
  padding: 7px 6px;
  border-radius: 8px;
  cursor: pointer;
  &.active, &:hover { background: color-mix(in srgb, var(--accent) 10%, transparent); }
}

.stock-code { color: var(--text-emphasis); font-weight: 700; }
.stock-name, .muted, .full-name { color: var(--text-secondary); font-size: 12px; }
.market-badge, .count-badge, .mkt-session-badge, .factor-score-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--accent) 18%, var(--border-soft));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface-muted));
  color: var(--text-secondary);
}

.spark-svg { width: 60px; height: 22px; }
.change-pill {
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, currentColor 32%, transparent);
  background: color-mix(in srgb, currentColor 12%, transparent);
}
.change-pill.up { color: var(--stat-up); }
.change-pill.down { color: var(--stat-down); }
.idx-price, .idx-change, .price-val, .cash-stat-capsule strong, .book-row {
  font-variant-numeric: tabular-nums;
}
.sort-tab { cursor: pointer; font-size: 12px; color: var(--text-secondary); &.active { color: var(--accent); } }
.group-select-btn { cursor: pointer; color: var(--text-emphasis); font-size: 12px; }

.big-symbol { font-size: 22px; font-weight: 800; color: var(--text-emphasis); margin-right: 8px; }
.main-price-num { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; }

.quote-metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
}

.q-cell {
  display: grid;
  gap: 2px;
  span { color: var(--text-muted); font-size: 11px; }
}

.period-toggle-btn, .r-pill, .side-btn {
  border: 1px solid var(--border-soft);
  background: var(--surface-soft);
  color: var(--text-primary);
  border-radius: 7px;
  padding: 4px 8px;
  cursor: pointer;
}

.period-toggle-btn.active, .side-btn.active {
  border-color: var(--accent);
  color: var(--text-emphasis);
}

.chart-canvas-container, .echarts-inner-dom {
  height: 320px;
  width: 100%;
}

.buy-btn.active { background: color-mix(in srgb, var(--stat-up) 18%, transparent); }
.sell-btn.active { background: color-mix(in srgb, var(--stat-down) 18%, transparent); }
.btn-order-buy { width: 100%; background: var(--order-buy-solid) !important; border: 0 !important; color: #fff !important; }
.btn-order-sell { width: 100%; background: var(--order-sell-solid) !important; border: 0 !important; color: #fff !important; }

.quick-trade-card, .right-pane { display: grid; gap: 8px; }
.ratio-pill-row, .period-button-group, .indicator-group-wrap, .trade-side-switcher { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }

.book-mid { text-align: center; padding: 6px 0; color: var(--text-emphasis); font-weight: 700; }
.range-track { display: grid; grid-template-columns: auto 1fr auto; gap: 6px; align-items: center; }
.track-bg { position: relative; height: 4px; border-radius: 99px; background: var(--surface-muted); }
.track-bg i { position: absolute; top: -3px; width: 10px; height: 10px; border-radius: 50%; background: var(--accent); }

@media (max-width: 1280px) {
  .terminal-main-grid { grid-template-columns: 1fr; }
  .watchlist-body { max-height: 280px; }
}
</style>
