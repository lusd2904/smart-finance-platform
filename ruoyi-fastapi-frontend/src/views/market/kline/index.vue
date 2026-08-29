<template>
  <div class="app-container market-kline">
    <el-row :gutter="16">
      <!-- 左侧标的选择 -->
      <el-col :xs="24" :sm="6" :md="5">
        <el-card shadow="never" class="side-card" v-loading="instLoading">
          <template #header>
            <div class="side-header">
              <span class="side-title">标的列表</span>
              <el-input v-model="instFilter" placeholder="搜索代码/名称" clearable size="small" style="width: 130px" />
            </div>
          </template>
          <el-scrollbar height="640px">
            <div v-for="group in groupedInstruments" :key="group.category" class="inst-group">
              <div class="group-name">{{ group.label }}</div>
              <div
                v-for="item in group.list"
                :key="item.symbol + item.market"
                class="inst-item"
                :class="{ active: current && current.symbol === item.symbol && current.market === item.market }"
                @click="selectInstrument(item)"
              >
                <span class="inst-symbol">{{ item.symbol }}</span>
                <span class="inst-name">{{ item.name }}</span>
              </div>
            </div>
            <el-empty v-if="groupedInstruments.length === 0" description="暂无标的" :image-size="60" />
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 右侧行情图 -->
      <el-col :xs="24" :sm="18" :md="19">
        <el-card shadow="never" class="chart-card" v-loading="klineLoading">
          <template #header>
            <div class="chart-header">
              <div class="chart-title">
                <span class="cur-name">{{ current ? current.name : '请选择标的' }}</span>
                <span class="cur-symbol" v-if="current">{{ current.symbol }} · {{ marketLabel(current.market) }}</span>
                <el-tag v-if="liveQuote" size="small" class="live-tag" effect="plain" :type="liveTone">
                  LIVE {{ fmtLiveLast(liveQuote.last) }} {{ fmtLivePct(liveQuote.changePct) }}
                </el-tag>
              </div>
              <div class="chart-actions">
                <el-radio-group v-model="period" size="small" @change="loadKline">
                  <el-radio-button label="daily">日K</el-radio-button>
                  <el-radio-button label="weekly">周K</el-radio-button>
                  <el-radio-button label="monthly">月K</el-radio-button>
                </el-radio-group>
                <el-button size="small" type="primary" plain icon="Refresh" :loading="syncLoading" @click="handleSync" v-hasPermi="['market:sync']">手动同步</el-button>
                <el-button size="small" :disabled="!current" @click="goDetail">详情</el-button>
                <el-button size="small" :disabled="!current" @click="goTradingview">高级图</el-button>
                <el-button size="small" type="success" icon="MagicStick" :loading="aiLoading" :disabled="!current" @click="handleAiAnalyze" v-hasPermi="['market:ai:analyze']">AI分析</el-button>
              </div>
            </div>
          </template>

          <!-- 指标选择 -->
          <div class="indicator-bar">
            <div class="ind-block">
              <span class="ind-label">主图叠加：</span>
              <el-checkbox-group v-model="mainOverlays" @change="renderChart">
                <el-checkbox value="MA">MA均线</el-checkbox>
                <el-checkbox value="EMA">EMA</el-checkbox>
                <el-checkbox value="BOLL">BOLL</el-checkbox>
              </el-checkbox-group>
            </div>
            <div class="ind-block">
              <span class="ind-label">副图指标：</span>
              <el-radio-group v-model="subIndicator" @change="renderChart">
                <el-radio-button label="VOL">成交量</el-radio-button>
                <el-radio-button label="MACD">MACD</el-radio-button>
                <el-radio-button label="RSI">RSI</el-radio-button>
                <el-radio-button label="KDJ">KDJ</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div ref="chartRef" class="kline-chart"></div>
          <el-empty v-if="!current" description="从左侧选择一个标的查看行情" />
        </el-card>
      </el-col>
    </el-row>

    <!-- AI研判弹窗 -->
    <el-dialog title="AI 行情研判" v-model="aiOpen" width="640px" append-to-body>
      <div v-loading="aiLoading">
        <el-descriptions :column="2" border v-if="aiResult">
          <el-descriptions-item label="建议">
            <el-tag :color="trendColor(aiResult.recommendation || aiResult.stance)" effect="dark" style="border:none;color:#fff">{{ aiResult.recommendation || '--' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="立场">{{ aiResult.stance || '--' }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ aiResult.confidence ?? '--' }}%</el-descriptions-item>
          <el-descriptions-item label="选股分">{{ aiResult.pickScore ?? '--' }}</el-descriptions-item>
        </el-descriptions>
        <div class="ai-section" v-if="aiResult && aiResult.summary">
          <div class="ai-title">综合研判</div>
          <div class="ai-body">{{ aiResult.summary }}</div>
        </div>
        <div class="ai-section" v-if="aiResult && aiResult.indicatorReview">
          <div class="ai-title">指标解读</div>
          <div class="ai-body">{{ aiResult.indicatorReview }}</div>
        </div>
        <div class="ai-section" v-if="aiResult && aiResult.sentimentReview">
          <div class="ai-title">舆情解读</div>
          <div class="ai-body">{{ aiResult.sentimentReview }}</div>
        </div>
        <div class="ai-section" v-if="aiResult && aiResult.operationAdvice">
          <div class="ai-title">操作建议</div>
          <div class="ai-body">{{ aiResult.operationAdvice }}</div>
        </div>
        <div class="ai-section" v-if="aiResult && aiResult.riskWarning">
          <div class="ai-title">风险提示</div>
          <div class="ai-body">{{ aiResult.riskWarning }}</div>
        </div>
        <el-empty v-if="!aiResult && !aiLoading" description="暂无研判结果" :image-size="70" />
      </div>
      <template #footer>
        <el-button @click="aiOpen = false">关 闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="MarketKline">
import echarts from '@/utils/echarts'
import { applyChartTheme } from '@/utils/echartsTheme';
import { listInstrument, getKline, getIndicators, syncMarket, aiAnalyze, getLatestAi, pollMarketJob } from '@/api/market';
import { getQuotesHub } from '@/composables/useMarketQuotesWs'

const { proxy } = getCurrentInstance();
const router = useRouter();

function goDetail() {
  if (!current.value) return;
  router.push({ path: '/market/symbol', query: { symbol: current.value.symbol, market: current.value.market || 'US' } });
}
function goTradingview() {
  if (!current.value) return;
  router.push({ path: '/market/tradingview', query: { symbol: current.value.symbol, market: current.value.market || 'US' } });
}

const CATEGORY_MAP = {
  index: '三大指数',
  giant: '七巨头',
  star: '明星股',
  semiconductor: '半导体',
  software: '软件'
};

const instruments = ref([]);
const instLoading = ref(false);
const instFilter = ref('');
const current = ref(null);

const period = ref('daily');
const klineData = ref([]);
const indicators = ref({});
const klineLoading = ref(false);
const syncLoading = ref(false);

const chartRef = ref(null);
let chart = null;

const mainOverlays = ref(['MA']);
const subIndicator = ref('VOL');

const aiOpen = ref(false);
const aiLoading = ref(false);
const aiResult = ref(null);

/** 按分类分组的标的（含搜索过滤） */
const groupedInstruments = computed(() => {
  const kw = instFilter.value.trim().toLowerCase();
  const filtered = instruments.value.filter(it => {
    if (!kw) return true;
    return String(it.symbol).toLowerCase().includes(kw) || String(it.name).toLowerCase().includes(kw);
  });
  const groups = {};
  filtered.forEach(it => {
    const cat = it.category || 'other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(it);
  });
  const order = ['index', 'giant', 'star', 'semiconductor', 'software'];
  const result = [];
  order.forEach(cat => {
    if (groups[cat]) {
      result.push({ category: cat, label: CATEGORY_MAP[cat] || cat, list: groups[cat] });
      delete groups[cat];
    }
  });
  Object.keys(groups).forEach(cat => {
    result.push({ category: cat, label: CATEGORY_MAP[cat] || cat, list: groups[cat] });
  });
  return result;
});

function marketLabel(market) {
  const m = { us: '美股', hk: '港股', a: 'A股', cn: 'A股' };
  return m[String(market).toLowerCase()] || market || '';
}

function trendColor(trend) {
  if (!trend) return '#909399';
  const t = String(trend);
  if (t.includes('多') || t.includes('涨') || t.includes('bull') || t.includes('看涨') || t.includes('上')) return '#f56c6c';
  if (t.includes('空') || t.includes('跌') || t.includes('bear') || t.includes('看跌') || t.includes('下')) return '#67c23a';
  return '#909399';
}

/** 加载标的列表 */
function loadInstruments() {
  instLoading.value = true;
  listInstrument().then(response => {
    instruments.value = response.data || response.rows || [];
    instLoading.value = false;
    if (instruments.value.length > 0 && !current.value) {
      selectInstrument(instruments.value[0]);
    }
  }).catch(() => {
    instLoading.value = false;
  });
}

const liveQuote = ref(null)
const liveTone = computed(() => {
  const n = Number(liveQuote.value && liveQuote.value.changePct)
  if (!Number.isFinite(n)) return 'info'
  return n >= 0 ? 'danger' : 'success'
})
let unsubQuotes = null
function fmtLiveLast(v) { const n = Number(v); return Number.isFinite(n) ? n.toFixed(2) : '--' }
function fmtLivePct(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return ''
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`
}
function quoteMatches(q, sym, mkt) {
  return String(q.symbol || '').toUpperCase() === String(sym || '').toUpperCase()
    && String(q.market || 'US').toUpperCase() === String(mkt || 'US').toUpperCase()
}
function lastBarIsRecent(dateStr) {
  const day = String(dateStr || '').slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return true
  const t = Date.parse(`${day}T00:00:00`)
  return Number.isFinite(t) && Date.now() - t < 48 * 3600 * 1000
}
function patchLastBar(quote) {
  const last = Number(quote && quote.last)
  const list = klineData.value || []
  if (!Number.isFinite(last) || !list.length) return
  const idx = list.length - 1
  const row = list[idx]
  if (!row) return
  if (/^\d{4}-\d{2}-\d{2}/.test(String(row.date || '')) && !lastBarIsRecent(row.date)) return
  if (Number(row.close) === last) return
  list.splice(idx, 1, { ...row, close: last, low: Math.min(Number(row.low), last), high: Math.max(Number(row.high), last) })
  renderChart()
}
function dropQuoteSub() {
  if (unsubQuotes) { unsubQuotes(); unsubQuotes = null }
  liveQuote.value = null
}
function syncQuoteSub() {
  dropQuoteSub()
  const cur = current.value
  if (!cur || !cur.symbol) return
  unsubQuotes = getQuotesHub().subscribeQuotes([{ symbol: cur.symbol, market: cur.market || 'US' }], (payload) => {
    const hit = ((payload && payload.items) || []).find(q => quoteMatches(q, current.value && current.value.symbol, current.value && current.value.market))
    if (!hit) return
    liveQuote.value = { last: hit.last, changePct: hit.changePct ?? hit.changeRate, quoteTime: hit.quoteTime }
    patchLastBar(hit)
  })
}

/** 选择标的 */
function selectInstrument(item) {
  current.value = item;
  loadKline();
  loadIndicators();
  syncQuoteSub();
}

/** 加载K线 */
function loadKline() {
  if (!current.value) return;
  klineLoading.value = true;
  getKline({ symbol: current.value.symbol, market: current.value.market, period: period.value }).then(response => {
    const d = response.data || {};
    klineData.value = d.klines || d.list || response.rows || (Array.isArray(d) ? d : []);
    klineLoading.value = false;
    renderChart();
  }).catch(() => {
    klineLoading.value = false;
  });
}

/** 加载技术指标 */
function loadIndicators() {
  if (!current.value) return;
  getIndicators({ symbol: current.value.symbol, market: current.value.market }).then(response => {
    indicators.value = response.data || {};
    renderChart();
  }).catch(() => {
    indicators.value = {};
  });
}

/** 取指标序列（兼容不同命名） */
function indSeries(...keys) {
  const src = indicators.value || {};
  for (const k of keys) {
    if (src[k] != null) return src[k];
  }
  return null;
}

/** 渲染K线图 */
function renderChart() {
  if (!chartRef.value || !current.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
  }
  const list = klineData.value || [];
  const dates = list.map(d => d.date);
  // candlestick 需要 [open, close, low, high]
  const candle = list.map(d => [d.open, d.close, d.low, d.high]);
  const volumes = list.map((d, i) => [i, d.volume, d.close >= d.open ? 1 : -1]);

  const legendData = ['K线'];
  const series = [
    {
      name: 'K线',
      type: 'candlestick',
      data: candle,
      itemStyle: {
        color: '#f56c6c', color0: '#67c23a',
        borderColor: '#f56c6c', borderColor0: '#67c23a'
      }
    }
  ];

  // 主图叠加指标
  const lineColors = { MA5: '#e6a23c', MA10: '#409eff', MA20: '#9254de', MA30: '#f56c6c', MA60: '#13c2c2' };
  if (mainOverlays.value.includes('MA')) {
    const maObj = indSeries('MA', 'ma') || {};
    Object.keys(maObj).forEach(key => {
      const name = key.toUpperCase().startsWith('MA') ? key.toUpperCase() : 'MA' + key;
      legendData.push(name);
      series.push({ name, type: 'line', data: maObj[key], smooth: true, showSymbol: false, lineWidth: 1, itemStyle: { color: lineColors[name] || '#888' } });
    });
  }
  if (mainOverlays.value.includes('EMA')) {
    const emaObj = indSeries('EMA', 'ema') || {};
    Object.keys(emaObj).forEach(key => {
      const name = key.toUpperCase().startsWith('EMA') ? key.toUpperCase() : 'EMA' + key;
      legendData.push(name);
      series.push({ name, type: 'line', data: emaObj[key], smooth: true, showSymbol: false, lineStyle: { type: 'dashed' }, itemStyle: { color: '#606266' } });
    });
  }
  if (mainOverlays.value.includes('BOLL')) {
    const boll = indSeries('BOLL', 'boll') || {};
    const map = { upper: 'BOLL上轨', mid: 'BOLL中轨', middle: 'BOLL中轨', lower: 'BOLL下轨' };
    ['upper', 'mid', 'middle', 'lower'].forEach(k => {
      if (boll[k]) {
        const name = map[k];
        legendData.push(name);
        series.push({ name, type: 'line', data: boll[k], smooth: true, showSymbol: false, lineWidth: 1, itemStyle: { color: k === 'upper' ? '#f56c6c' : k === 'lower' ? '#67c23a' : '#909399' } });
      }
    });
  }

  // 副图
  const subLegend = [];
  buildSubSeries(series, subLegend);

  const option = {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: legendData.concat(subLegend), top: 0, type: 'scroll' },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 50, right: 20, top: 40, height: '52%' },
      { left: 50, right: 20, top: '66%', height: '22%' }
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: true, axisLine: { onZero: false }, axisTick: { show: false }, axisLabel: { show: false }, min: 'dataMin', max: 'dataMax' }
    ],
    yAxis: [
      { scale: true, splitArea: { show: false } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: true }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { show: true, type: 'slider', xAxisIndex: [0, 1], bottom: 8, start: 60, end: 100 }
    ],
    series
  };
  chart.setOption(applyChartTheme(option), true);
}

/** 构建副图 series */
function buildSubSeries(series, subLegend) {
  const list = klineData.value || [];
  const dates = list.map(d => d.date);
  if (subIndicator.value === 'VOL') {
    const volObj = indSeries('VOL', 'vol') || {};
    subLegend.push('成交量');
    series.push({
      name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
      data: list.map(d => ({ value: d.volume, itemStyle: { color: d.close >= d.open ? '#f56c6c' : '#67c23a' } }))
    });
    // 成交量均线
    ['MAVOL5', 'MAVOL10', 'ma5', 'ma10'].forEach((k, idx) => {
      if (volObj[k]) {
        const name = 'VOL' + k.toUpperCase().replace('MAVOL', 'MA').replace('MA', 'MA');
        subLegend.push(name);
        series.push({ name, type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: volObj[k], showSymbol: false, lineWidth: 1, itemStyle: { color: idx === 0 ? '#e6a23c' : '#409eff' } });
      }
    });
  } else if (subIndicator.value === 'MACD') {
    const macd = indSeries('MACD', 'macd') || {};
    subLegend.push('DIF', 'DEA', 'MACD');
    series.push({ name: 'DIF', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macd.dif || macd.DIF, showSymbol: false, lineWidth: 1, itemStyle: { color: '#e6a23c' } });
    series.push({ name: 'DEA', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macd.dea || macd.DEA, showSymbol: false, lineWidth: 1, itemStyle: { color: '#409eff' } });
    const bar = macd.macd || macd.bar || macd.hist || [];
    series.push({
      name: 'MACD', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
      data: (bar || []).map(v => ({ value: v, itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' } }))
    });
  } else if (subIndicator.value === 'RSI') {
    const rsi = indSeries('RSI', 'rsi') || {};
    Object.keys(rsi).forEach((k, idx) => {
      const name = k.toUpperCase().startsWith('RSI') ? k.toUpperCase() : 'RSI' + k;
      subLegend.push(name);
      series.push({ name, type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: rsi[k], showSymbol: false, lineWidth: 1, itemStyle: { color: ['#e6a23c', '#409eff', '#9254de'][idx % 3] } });
    });
  } else if (subIndicator.value === 'KDJ') {
    const kdj = indSeries('KDJ', 'kdj') || {};
    const map = { k: 'K', d: 'D', j: 'J' };
    ['k', 'd', 'j'].forEach((key, idx) => {
      const arr = kdj[key] || kdj[key.toUpperCase()];
      if (arr) {
        subLegend.push(map[key]);
        series.push({ name: map[key], type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: arr, showSymbol: false, lineWidth: 1, itemStyle: { color: ['#e6a23c', '#409eff', '#f56c6c'][idx] } });
      }
    });
  }
}

/** 手动同步 */
function handleSync() {
  syncLoading.value = true;
  syncMarket(current.value ? { symbol: current.value.symbol } : {}).then(res => {
    const d = res.data || {};
    proxy.$modal.msgSuccess(res.msg || (d.accepted ? '已加入后台队列' : `同步完成，标的 ${d.syncedSymbols ?? '-'} 个`));
    if (!d.accepted) {
      loadKline();
      loadIndicators();
    }
  }).finally(() => {
    syncLoading.value = false;
  });
}

function mapAiResult(data) {
  return {
    recommendation: data.recommendation || data.finalDecision,
    stance: data.stance || data.trend,
    confidence: data.confidence ?? data.finalConfidence,
    pickScore: data.pickScore,
    factorScore: data.factorScore,
    summary: data.summary || data.summaryText,
    indicatorReview: data.indicatorReview || data.result?.indicator_review,
    sentimentReview: data.sentimentReview || data.result?.sentiment_review,
    operationAdvice: data.operationAdvice || data.advice || data.result?.operation_advice,
    riskWarning: data.riskWarning || data.result?.risk_warning
  };
}

/** AI分析 */
async function handleAiAnalyze() {
  if (!current.value) return;
  aiOpen.value = true;
  aiLoading.value = true;
  aiResult.value = null;
  try {
    const res = await aiAnalyze({ symbol: current.value.symbol, market: current.value.market });
    const data = res.data || {};
    if (data.accepted || data.jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队');
      if (data.jobId) {
        const ticket = await pollMarketJob(data.jobId);
        if (ticket.status === 'failed') {
          proxy.$modal.msgError(ticket.error || '研判失败');
          return;
        }
      }
      const latest = await getLatestAi(current.value.symbol, { market: current.value.market });
      aiResult.value = mapAiResult(latest.data || {});
      return;
    }
    aiResult.value = mapAiResult(data);
  } finally {
    aiLoading.value = false;
  }
}

let resizeTimer = null;
function handleResize() {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    chart && chart.resize();
  }, 100);
}

onMounted(() => {
  loadInstruments();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  dropQuoteSub();
  if (resizeTimer) clearTimeout(resizeTimer);
  window.removeEventListener('resize', handleResize);
  if (chart) {
    chart.dispose();
    chart = null;
  }
});
</script>

<style lang="scss" scoped>
.market-kline {
  .side-card {
    border-radius: 12px;
    :deep(.el-card__body) { padding: 0 8px 8px; }
    .side-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      .side-title { font-size: 15px; font-weight: 600; color: var(--text-emphasis, #303133); }
    }
    .inst-group {
      margin-top: 8px;
      .group-name {
        font-size: 12px;
        color: #909399;
        padding: 6px 8px 4px;
        font-weight: 600;
        border-bottom: 1px dashed #ebeef5;
      }
    }
    .inst-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 10px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.2s;
      &:hover { background: var(--surface-muted, #f5f7fa); }
      &.active { background: #ecf0ff; }
      .inst-symbol { font-size: 13px; font-weight: 600; color: var(--text-emphasis, #303133); }
      .inst-name {
        font-size: 12px; color: #909399;
        max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
    }
  }
  .chart-card {
    border-radius: 12px;
    .chart-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      .cur-name { font-size: 17px; font-weight: 700; color: var(--text-emphasis, #303133); }
      .cur-symbol { margin-left: 10px; font-size: 13px; color: #909399; }
      .live-tag { margin-left: 10px; vertical-align: middle; }
      .chart-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    }
    .indicator-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 24px;
      padding: 6px 0 14px;
      border-bottom: 1px solid #f0f2f5;
      margin-bottom: 8px;
      .ind-block { display: flex; align-items: center; gap: 8px; }
      .ind-label { font-size: 13px; color: #606266; font-weight: 600; }
    }
    .kline-chart {
      width: 100%;
      height: 560px;
    }
  }
  .ai-section {
    margin-top: 16px;
    .ai-title {
      font-size: 14px; font-weight: 600; color: var(--text-emphasis, #303133);
      margin-bottom: 8px; padding-left: 8px; border-left: 3px solid #409eff;
    }
    .ai-body { font-size: 13px; color: #606266; line-height: 1.8; white-space: pre-wrap; }
  }
}
</style>
