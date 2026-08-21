<template>
  <div class="app-container market-dashboard">
    <!-- 顶部操作栏 -->
    <div class="dash-header">
      <div class="dash-title">
        <span class="title-text">行情数据概览</span>
        <span class="title-sub">多市场标的行情监测</span>
      </div>
      <div class="dash-actions">
        <el-button type="primary" icon="Refresh" :loading="syncLoading" @click="handleSync" v-hasPermi="['market:sync']">同步行情</el-button>
        <el-button icon="RefreshRight" circle @click="loadAll" title="刷新" />
      </div>
    </div>

    <!-- 分类统计卡片 -->
    <el-row :gutter="16" class="mb16">
      <el-col :xs="12" :sm="8" :md="4" v-for="card in categoryCards" :key="card.key">
        <div class="stat-card" :style="{ background: card.bg }">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value">{{ card.count }}</div>
          <div class="stat-unit">个标的</div>
        </div>
      </el-col>
    </el-row>

    <!-- 三大指数走势 -->
    <el-card shadow="never" class="panel-card mb16" v-loading="indexLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">三大指数最新走势</span>
          <span class="panel-sub">近 60 个交易日收盘价</span>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :xs="24" :md="8" v-for="idx in indexList" :key="idx.symbol">
          <div class="index-block">
            <div class="index-head">
              <span class="index-name">{{ idx.name }}</span>
              <span class="index-symbol">{{ idx.symbol }}</span>
            </div>
            <div :ref="el => setMiniRef(idx.symbol, el)" class="mini-chart"></div>
          </div>
        </el-col>
      </el-row>
      <el-empty v-if="indexList.length === 0 && !indexLoading" description="暂无指数数据" :image-size="70" />
    </el-card>

    <!-- 标的清单 -->
    <el-card shadow="never" class="panel-card" v-loading="instLoading">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">标的清单</span>
          <span class="panel-sub">共 {{ instruments.length }} 个</span>
        </div>
      </template>
      <el-table :data="instruments" style="width: 100%" max-height="420">
        <el-table-column label="代码" prop="symbol" width="140" />
        <el-table-column label="名称" prop="name" />
        <el-table-column label="市场" prop="market" width="100" align="center">
          <template #default="scope">{{ marketLabel(scope.row.market) }}</template>
        </el-table-column>
        <el-table-column label="分类" prop="category" width="140" align="center">
          <template #default="scope">
            <el-tag effect="plain">{{ categoryLabel(scope.row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="scope">
            <el-button link type="primary" @click="openSymbol(scope.row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup name="MarketDashboard">
import * as echarts from 'echarts';
import { listInstrument, getKline, syncMarket } from '@/api/market';

const { proxy } = getCurrentInstance();
const router = useRouter();

function openSymbol(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } });
}

const CATEGORY_MAP = {
  index: '三大指数',
  mag7: '七巨头',
  star: '明星股',
  semiconductor: '半导体',
  software: '软件'
};
const CARD_BG = {
  index: 'linear-gradient(135deg, #409eff 0%, #2d6cdf 100%)',
  mag7: 'linear-gradient(135deg, #9254de 0%, #6a3fd0 100%)',
  star: 'linear-gradient(135deg, #f0a020 0%, #e0701a 100%)',
  semiconductor: 'linear-gradient(135deg, #13c2c2 0%, #08979c 100%)',
  software: 'linear-gradient(135deg, #f56c6c 0%, #d94747 100%)'
};

const instruments = ref([]);
const instLoading = ref(false);
const indexLoading = ref(false);
const syncLoading = ref(false);
const indexList = ref([]);

const miniRefs = {};
const miniCharts = {};

function setMiniRef(symbol, el) {
  if (el) miniRefs[symbol] = el;
}

function marketLabel(market) {
  const m = { us: '美股', hk: '港股', a: 'A股', cn: 'A股' };
  return m[String(market).toLowerCase()] || market || '';
}
function categoryLabel(cat) {
  return CATEGORY_MAP[cat] || cat || '其他';
}

/** 分类统计卡片 */
const categoryCards = computed(() => {
  const counts = {};
  instruments.value.forEach(it => {
    const c = it.category || 'other';
    counts[c] = (counts[c] || 0) + 1;
  });
  const order = ['index', 'mag7', 'star', 'semiconductor', 'software'];
  return order.map(key => ({
    key,
    label: CATEGORY_MAP[key],
    count: counts[key] || 0,
    bg: CARD_BG[key]
  }));
});

/** 加载全部 */
function loadAll() {
  loadInstruments();
}

function loadInstruments() {
  instLoading.value = true;
  listInstrument().then(response => {
    instruments.value = response.data || response.rows || [];
    instLoading.value = false;
    loadIndexTrends();
  }).catch(() => {
    instLoading.value = false;
  });
}

/** 加载三大指数走势 */
function loadIndexTrends() {
  const idxs = instruments.value.filter(it => it.category === 'index').slice(0, 3);
  indexList.value = idxs;
  if (idxs.length === 0) return;
  indexLoading.value = true;
  Promise.all(idxs.map(idx =>
    getKline({ symbol: idx.symbol, market: idx.market, period: 'daily' })
      .then(res => {
        const d = res.data || {};
        const rows = d.klines || d.rows || (Array.isArray(d) ? d : []) || res.rows || [];
        return { symbol: idx.symbol, data: rows.slice(-60) };
      })
      .catch(() => ({ symbol: idx.symbol, data: [] }))
  )).then(results => {
    indexLoading.value = false;
    nextTick(() => {
      results.forEach(r => renderMini(r.symbol, r.data));
    });
  });
}

function renderMini(symbol, data) {
  const el = miniRefs[symbol];
  if (!el) return;
  if (!miniCharts[symbol]) {
    miniCharts[symbol] = echarts.init(el);
  }
  const dates = data.map(d => d.date);
  const closes = data.map(d => d.close);
  const up = closes.length > 1 && closes[closes.length - 1] >= closes[0];
  const color = up ? '#f56c6c' : '#67c23a';
  miniCharts[symbol].setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 44, right: 12, top: 12, bottom: 24 },
    xAxis: { type: 'category', data: dates, boundaryGap: false, axisLabel: { formatter: v => String(v).slice(5) }, show: true },
    yAxis: { type: 'value', scale: true },
    series: [{ type: 'line', data: closes, smooth: true, showSymbol: false, itemStyle: { color }, areaStyle: { opacity: 0.1, color } }]
  });
}

/** 手动同步 */
function handleSync() {
  syncLoading.value = true;
  syncMarket({}).then(res => {
    const d = res.data || {};
    proxy.$modal.msgSuccess(res.msg || (d.accepted ? '已加入后台队列' : `同步完成，标的 ${d.syncedSymbols ?? '-'} 个`));
    if (!d.accepted) loadAll();
  }).finally(() => {
    syncLoading.value = false;
  });
}

function handleResize() {
  Object.values(miniCharts).forEach(c => c && c.resize());
}

onMounted(() => {
  loadAll();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  Object.values(miniCharts).forEach(c => c && c.dispose());
});
</script>

<style lang="scss" scoped>
.market-dashboard {
  .mb16 { margin-bottom: 16px; }
  .dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 8px;
    .title-text { font-size: 20px; font-weight: 700; color: var(--text-emphasis, #303133); }
    .title-sub { margin-left: 12px; font-size: 13px; color: #909399; }
  }
  .stat-card {
    border-radius: 14px;
    padding: 18px 20px;
    color: #fff;
    margin-bottom: 8px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
    .stat-label { font-size: 13px; opacity: 0.92; }
    .stat-value { font-size: 30px; font-weight: 700; line-height: 1.3; }
    .stat-unit { font-size: 12px; opacity: 0.85; }
  }
  .panel-card {
    border-radius: 14px;
    .panel-header {
      display: flex; align-items: baseline; justify-content: space-between;
      .panel-title { font-size: 15px; font-weight: 600; color: var(--text-emphasis, #303133); }
      .panel-sub { font-size: 12px; color: #909399; }
    }
  }
  .index-block {
    border: 1px solid #ebeef5;
    border-radius: 12px;
    padding: 12px 14px;
    margin-bottom: 8px;
    .index-head {
      display: flex; align-items: baseline; justify-content: space-between;
      .index-name { font-size: 14px; font-weight: 600; color: var(--text-emphasis, #303133); }
      .index-symbol { font-size: 12px; color: #909399; }
    }
    .mini-chart { width: 100%; height: 160px; }
  }
}
</style>
