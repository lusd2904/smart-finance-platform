<template>
  <PageFrame
    title="自选清单"
    subtitle="按登录账号隔离 · 三栏 list / K / detail · 对齐 /market/watchlist"
    badge="「自选清单 /market/watchlist」"
    :loading="loading"
  >
    <template #actions>
      <el-button type="primary" @click="open = true">+ 新增自选</el-button>
      <el-button type="success" :loading="analyzeAllLoading" @click="analyzeAll">立即分析全部</el-button>
      <el-button :loading="backtestLoading" @click="loadBacktest">建议回测</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip kpi-row">
      <article class="stat-tile glass-panel kpi-count">
        <span>自选数量</span>
        <strong class="numeric">{{ kpis.count }}</strong>
      </article>
      <article class="stat-tile glass-panel kpi-bull">
        <span>看多</span>
        <strong class="numeric">{{ kpis.bull }}</strong>
      </article>
      <article class="stat-tile glass-panel kpi-bear">
        <span>看空</span>
        <strong class="numeric">{{ kpis.bear }}</strong>
      </article>
      <article class="stat-tile glass-panel kpi-flat">
        <span>中性</span>
        <strong class="numeric">{{ kpis.neutral }}</strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel heat-placeholder">
      <template #header>
        <div class="card-head">
          <h3>自选相关热力</h3>
          <span class="muted">相关矩阵 · Pearson</span>
        </div>
      </template>
      <div v-if="corrOk" ref="corrRef" class="corr-chart" />
      <div v-else class="corr-empty">
        <span class="corr-icon" aria-hidden="true">▦</span>
        <p>Go data-api 简化相关矩阵：完整 Pearson 相关需 Influx 批量查询</p>
      </div>
    </el-card>

    <el-card v-if="backtest.count != null" shadow="never" class="glass-panel">
      <template #header>
        <div class="card-head">
          <h3>建议回测（1/5 日）</h3>
          <span class="muted">{{ backtest.message || '买入/加仓为多，减仓/卖出为空' }}</span>
        </div>
      </template>
      <el-table :data="backtest.items || []" size="small" max-height="240" empty-text="暂无买入/卖出类建议">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="recommendation" label="建议" width="80" />
        <el-table-column label="1日" width="90" align="right">
          <template #default="{ row }"><span class="numeric" :class="changeClass(row.fwd1)">{{ fmtChange((Number(row.fwd1) || 0) * 100) }}</span></template>
        </el-table-column>
        <el-table-column label="5日" width="90" align="right">
          <template #default="{ row }"><span class="numeric" :class="changeClass(row.fwd5)">{{ fmtChange((Number(row.fwd5) || 0) * 100) }}</span></template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="watch-shell">
      <aside class="pane glass-panel">
        <div class="chip-row">
          <button type="button" class="filter-chip" :class="{ active: group === '' }" @click="group = ''">全部 {{ items.length }}</button>
          <button
            v-for="g in groups"
            :key="g.name"
            type="button"
            class="filter-chip"
            :class="{ active: group === g.name }"
            @click="group = g.name"
          >{{ g.name }} {{ g.count }}</button>
        </div>
        <el-input v-model="keyword" clearable placeholder="搜索代码/名称" :prefix-icon="Search" />
        <div class="sym-list">
          <button
            v-for="row in filtered"
            :key="row.id || row.symbol"
            type="button"
            class="sym-row"
            :class="{ active: isCurrent(row) }"
            @click="selectRow(row)"
          >
            <div>
              <strong>{{ row.symbol }}</strong>
              <span class="muted">{{ row.name || '--' }} · {{ marketLabel(row.market) }}</span>
            </div>
            <div class="sym-quote">
              <span class="numeric">{{ fmtPx(row.last ?? row.price) }}</span>
              <em :class="changeClass(row.changeRate ?? row.changePct)">{{ fmtChange(row.changeRate ?? row.changePct) }}</em>
            </div>
          </button>
          <el-empty v-if="!filtered.length" description="暂无自选" :image-size="48" />
        </div>
      </aside>

      <section class="pane glass-panel mid-pane">
        <template v-if="current">
          <div class="mid-head">
            <div>
              <strong>{{ current.name || current.symbol }}</strong>
              <span class="muted">{{ current.symbol }} · {{ marketLabel(current.market) }}</span>
            </div>
            <div class="mid-acts">
              <el-radio-group v-model="period" size="small" @change="loadChart">
                <el-radio-button value="daily">日K</el-radio-button>
                <el-radio-button value="weekly">周K</el-radio-button>
                <el-radio-button value="monthly">月K</el-radio-button>
              </el-radio-group>
              <el-button link type="primary" @click="$router.push(terminalRoute(current))">详情</el-button>
              <el-button link type="success" :loading="analyzing" @click="analyzeOne(current)">分析</el-button>
              <el-button link type="danger" @click="remove(current)">移除</el-button>
            </div>
          </div>
          <div ref="chartRef" class="kline-chart" v-loading="chartLoading" />
        </template>
        <el-empty v-else description="选择左侧一只自选股查看走势" :image-size="72" />
      </section>

      <aside class="pane glass-panel detail-pane">
        <template v-if="current">
          <div class="detail-head">
            <el-tag size="small" effect="plain">{{ stanceLabel(current) }}</el-tag>
          </div>
          <div class="quote-line">
            <strong class="numeric" :class="changeClass(current.changeRate ?? current.changePct)">{{ fmtPx(current.last ?? current.price) }}</strong>
            <span :class="changeClass(current.changeRate ?? current.changePct)">{{ fmtChange(current.changeRate ?? current.changePct) }}</span>
          </div>
          <div class="meta-grid">
            <div><span>开盘</span><b class="numeric">{{ fmtPx(current.open) }}</b></div>
            <div><span>最高</span><b class="numeric up">{{ fmtPx(current.high) }}</b></div>
            <div><span>最低</span><b class="numeric down">{{ fmtPx(current.low) }}</b></div>
            <div><span>成交额</span><b class="numeric">{{ fmtAmount(current.turnover) }}</b></div>
            <div><span>市场</span><b>{{ marketLabel(current.market) }}</b></div>
            <div><span>分组</span><b>{{ groupText(current) }}</b></div>
          </div>
          <div class="ai-box">
            <h4>AI 立场 · {{ stanceLabel(current) }}</h4>
            <p>{{ current.summary || current.aiSummary || current.note || '暂无分析摘要，请点「分析」。' }}</p>
            <div class="ai-acts">
              <el-button link type="primary" @click="goAiChat($router, current)">跳转分析</el-button>
              <el-button link type="primary" @click="loadBacktest">建议回测</el-button>
            </div>
          </div>
        </template>
        <el-empty v-else description="选择左侧一只自选股查看详情" :image-size="56" />
      </aside>
    </div>

    <button v-if="!showScan" type="button" class="compare-link" @click="showScan = true">扫描表（次要）</button>
    <el-card v-if="showScan" shadow="never" class="glass-panel">
      <template #header>
        <div class="card-head">
          <h3>扫描表</h3>
          <el-button link @click="showScan = false">收起</el-button>
        </div>
      </template>
      <el-table :data="filtered" stripe empty-text="暂无自选" @row-click="selectRow">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column label="最新价" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtPx(row.last ?? row.price) }}</span></template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate ?? row.changePct)">{{ fmtChange(row.changeRate ?? row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="立场" width="80">
          <template #default="{ row }">{{ stanceLabel(row) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="open" title="新增自选" width="420px">
      <el-form label-width="72px">
        <el-form-item label="市场">
          <el-select v-model="form.market" style="width:100%">
            <el-option label="美股 US" value="US" />
            <el-option label="港股 HK" value="HK" />
            <el-option label="A股 CN" value="CN" />
          </el-select>
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model="form.symbol" placeholder="AAPL / 00700 / 600519" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="form.group" placeholder="可选，如 核心持仓" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="add">确定</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span class="legend-dots">
        <span><i class="dot-up" /> 涨红</span>
        <span><i class="dot-down" /> 跌绿</span>
      </span>
      <span>tabular-nums · glass-panel · 三栏默认 · 扫描表次要 · 账号隔离 watchlist API</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import PageFrame from '@/components/page/PageFrame.vue'
import {
  addMarketWatchlist,
  analyzeMarketWatchlist,
  delMarketWatchlist,
  getKline,
  getMarketWatchlistBacktest,
  getMarketWatchlistOverview,
  getWatchlistCorrelation,
  listMarketWatchlist
} from '@/api/market'
import { changeClass, fmtAmount, fmtChange, fmtPx } from '@/utils/format'
import { goAiChat, marketLabel, unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'
import { stubKline, stubWatchlist } from '@/utils/stubs'

const loading = ref(false)
const saving = ref(false)
const analyzeAllLoading = ref(false)
const analyzing = ref(false)
const backtestLoading = ref(false)
const chartLoading = ref(false)
const keyword = ref('')
const group = ref('')
const items = ref([])
const overview = ref({})
const current = ref(null)
const period = ref('daily')
const open = ref(false)
const showScan = ref(false)
const backtest = ref({})
const corr = ref({ symbols: [] })
const form = reactive({ market: 'US', symbol: '', group: '' })
const chartRef = ref(null)
const corrRef = ref(null)
let chart
let corrChart

function rowGroups(row) {
  return row.groups || row.groupNames || (row.group ? [row.group] : [])
}
function groupText(row) {
  return rowGroups(row).filter((n) => n && n !== '全部').join('、') || '未分组'
}
function stanceOf(row) {
  const raw = String(row.recommendation || row.aiVerdict || row.stance || '').toLowerCase()
  if (['买入', '加仓', '看多', '偏多', 'bull'].some((k) => raw.includes(k))) return 'bull'
  if (['卖出', '减仓', '看空', '偏空', 'bear'].some((k) => raw.includes(k))) return 'bear'
  if (['观望', 'wait'].some((k) => raw.includes(k))) return 'wait'
  const chg = Number(row.changeRate ?? row.changePct)
  if (chg > 1) return 'bull'
  if (chg < -1) return 'bear'
  return 'neutral'
}
function stanceLabel(row) {
  return { bull: '看多', bear: '看空', wait: '观望', neutral: '中性' }[stanceOf(row)] || '观望'
}
function isCurrent(row) {
  if (!current.value) return false
  return (row.id && row.id === current.value.id) || (row.symbol === current.value.symbol && row.market === current.value.market)
}

const groups = computed(() => {
  const map = {}
  for (const item of items.value) {
    for (const name of rowGroups(item)) {
      if (!name || name === '全部') continue
      map[name] = (map[name] || 0) + 1
    }
  }
  return Object.entries(map).map(([name, count]) => ({ name, count }))
})
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return items.value.filter((r) => {
    const groupOk = !group.value || rowGroups(r).includes(group.value)
    return groupOk && (!kw || `${r.symbol} ${r.name || ''}`.toLowerCase().includes(kw))
  })
})
const kpis = computed(() => {
  const ov = overview.value || {}
  if (ov.bullish != null || ov.count != null) {
    return {
      count: ov.count ?? items.value.length,
      bull: ov.bullish ?? 0,
      bear: ov.bearish ?? 0,
      neutral: ov.neutral ?? 0
    }
  }
  const stance = items.value.map(stanceOf)
  return {
    count: items.value.length,
    bull: stance.filter((s) => s === 'bull').length,
    bear: stance.filter((s) => s === 'bear').length,
    neutral: stance.filter((s) => s === 'neutral' || s === 'wait').length
  }
})
const corrOk = computed(() => (corr.value.symbols || []).length >= 2)

function quotePalette() {
  const styles = getComputedStyle(document.documentElement)
  return {
    up: styles.getPropertyValue('--stat-up').trim() || '#ff0055',
    down: styles.getPropertyValue('--stat-down').trim() || '#39ff14'
  }
}

function renderChart(rows) {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const dark = document.documentElement.dataset.theme !== 'glass-light'
  const { up, down } = quotePalette()
  const cats = rows.map((b, i) => String(b.date || b.time || b.t || i).slice(5))
  const ohlc = rows.map((b) => [b.open ?? b[1], b.close ?? b[2], b.low ?? b[3], b.high ?? b[4]])
  chart.setOption({
    backgroundColor: 'transparent',
    animation: false,
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 12, top: 16, bottom: 28 },
    xAxis: { type: 'category', data: cats, axisLine: { lineStyle: { color: '#64748b' } } },
    yAxis: { scale: true, splitLine: { lineStyle: { color: dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' } } },
    series: [{ type: 'candlestick', data: ohlc, itemStyle: { color: up, color0: down, borderColor: up, borderColor0: down } }]
  }, true)
}

async function loadChart() {
  if (!current.value) return
  chartLoading.value = true
  try {
    const res = await getKline({ symbol: current.value.symbol, market: current.value.market || 'US', period: period.value })
    const raw = unwrap(res)
    const rows = raw.klines || raw.rows || raw.items || raw.list || []
    await nextTick()
    renderChart(rows.length ? rows : stubKline(current.value.last ?? current.value.price))
  } catch {
    await nextTick()
    renderChart(stubKline(current.value.last ?? current.value.price))
  } finally {
    chartLoading.value = false
  }
}

function renderCorr() {
  const symbols = corr.value.symbols || []
  const names = corr.value.names || symbols
  const matrix = corr.value.matrix || []
  if (symbols.length < 2 || !corrRef.value) return
  if (!corrChart) corrChart = echarts.init(corrRef.value)
  const labels = names.map((n, i) => n || symbols[i])
  const data = []
  matrix.forEach((row, i) => {
    (row || []).forEach((v, j) => {
      if (v == null) return
      data.push([j, i, Number(v)])
    })
  })
  corrChart.setOption({
    tooltip: { formatter: (p) => `${labels[p.value[1]]} × ${labels[p.value[0]]}: ${Number(p.value[2]).toFixed(2)}` },
    grid: { left: 56, right: 16, top: 8, bottom: 36 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
    visualMap: { min: -1, max: 1, orient: 'horizontal', left: 'center', inRange: { color: ['#16a34a', '#f8fafc', '#dc2626'] } },
    series: [{ type: 'heatmap', data, label: { show: false } }]
  }, true)
}

function selectRow(row) {
  current.value = row
  nextTick(loadChart)
}

function applyStub() {
  items.value = stubWatchlist()
  overview.value = {}
  current.value = items.value[0] || null
  nextTick(loadChart)
}

async function load() {
  loading.value = true
  try {
    const [listRes, ovRes] = await Promise.allSettled([listMarketWatchlist(), getMarketWatchlistOverview()])
    let rows = []
    if (listRes.status === 'fulfilled') rows = unwrapList(listRes.value)
    if (ovRes.status === 'fulfilled') {
      const ov = unwrap(ovRes.value)
      overview.value = ov
      if (!rows.length) rows = ov.items || ov.watchlist || []
    }
    if (!rows.length) {
      applyStub()
      return
    }
    items.value = rows
    const keep = current.value && rows.find((r) => isCurrent(r))
    current.value = keep || rows[0]
    nextTick(loadChart)
    loadCorrelation()
  } catch {
    applyStub()
  } finally {
    loading.value = false
  }
}

async function loadCorrelation() {
  try {
    const res = await getWatchlistCorrelation({ days: 60, limit: 12 })
    corr.value = unwrap(res) || { symbols: [] }
    await nextTick()
    if (corrOk.value) renderCorr()
  } catch {
    corr.value = { symbols: [], message: '相关矩阵暂不可用' }
  }
}

async function loadBacktest() {
  backtestLoading.value = true
  try {
    backtest.value = unwrap(await getMarketWatchlistBacktest({ limit: 200 }))
    if (!backtest.value.items) backtest.value = { ...backtest.value, count: backtest.value.count ?? 0, items: backtest.value.items || [] }
  } catch {
    ElMessage.info('回测暂不可用')
  } finally {
    backtestLoading.value = false
  }
}

async function analyzeAll() {
  if (!items.value.length) {
    ElMessage.warning('请先添加自选股')
    return
  }
  analyzeAllLoading.value = true
  try {
    const res = await analyzeMarketWatchlist({ refreshContent: true })
    ElMessage.success(res.msg || '已提交分析')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzeAllLoading.value = false
  }
}

async function analyzeOne(row) {
  analyzing.value = true
  try {
    const res = await analyzeMarketWatchlist({ symbol: row.symbol, market: row.market, refreshContent: true })
    ElMessage.success(res.msg || '分析完成')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

async function add() {
  if (!form.symbol.trim()) {
    ElMessage.warning('请输入代码')
    return
  }
  saving.value = true
  try {
    await addMarketWatchlist({
      symbol: form.symbol.trim(),
      market: form.market,
      groups: form.group ? [form.group] : undefined,
      note: form.group || '自选'
    })
    ElMessage.success('已加入自选')
    open.value = false
    form.symbol = ''
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '添加失败')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await delMarketWatchlist(row.id || row.watchlistId || row.symbol)
    ElMessage.success('已删除')
    current.value = null
    load()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

watch(filtered, (rows) => {
  if (current.value && !rows.some(isCurrent) && rows[0]) selectRow(rows[0])
})

onMounted(load)
onUnmounted(() => {
  chart?.dispose()
  corrChart?.dispose()
})
</script>

<style scoped>
.kpi-row { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.kpi-count strong { color: var(--accent); }
.kpi-bull { background: color-mix(in srgb, var(--stat-up) 12%, transparent); }
.kpi-bear { background: color-mix(in srgb, var(--stat-down) 12%, transparent); }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
h3, h4 { margin: 0; font-size: 15px; }
.heat-placeholder .corr-empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  text-align: center;
  color: var(--text-secondary);
  gap: 6px;
}
.corr-icon { font-size: 28px; opacity: 0.45; }
.corr-chart { height: 220px; }
.watch-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1.5fr) 280px;
  gap: 10px;
  min-height: 520px;
}
.pane { padding: 10px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.sym-list { overflow: auto; flex: 1; }
.sym-row {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.sym-row.active {
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
}
.sym-row div:first-child { display: grid; }
.sym-quote { text-align: right; display: grid; }
.mid-head, .mid-acts { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; }
.kline-chart { flex: 1; min-height: 360px; }
.quote-line { display: flex; align-items: baseline; gap: 10px; }
.quote-line strong { font-size: 28px; }
.meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
.meta-grid span { display: block; color: var(--text-secondary); font-size: 12px; }
.ai-box {
  margin-top: 8px;
  padding: 10px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}
.ai-box p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.ai-acts { display: flex; gap: 8px; margin-top: 6px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.compare-link {
  margin-top: 8px;
  background: none;
  border: 0;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
}
@media (max-width: 1100px) {
  .watch-shell { grid-template-columns: 1fr; }
  .kline-chart { min-height: 280px; }
}
</style>
