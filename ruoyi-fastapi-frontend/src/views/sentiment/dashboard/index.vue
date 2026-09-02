<template>
  <div class="app-container sentiment-dashboard">
    <!-- 顶部操作栏 -->
    <div class="dash-header">
      <div class="dash-title">
        <span class="title-text">舆情AI分析大盘</span>
        <span class="title-sub" v-if="latestAnalysisTime">最新分析时间：{{ latestAnalysisTime }}</span>
      </div>
      <div class="dash-actions">
        <el-button type="primary" icon="Download" :loading="collectLoading" @click="handleCollect" v-hasPermi="['sentiment:news:collect']">立即采集</el-button>
        <el-button type="success" icon="MagicStick" :loading="analyzeLoading" :disabled="!!rateLimitedUntil" @click="handleAnalyze" v-hasPermi="['sentiment:analysis:run']">
          {{ rateLimitedUntil ? `请稍后重试 (${retryLeft}s)` : '立即分析' }}
        </el-button>
        <el-button icon="Refresh" circle @click="refreshAll" title="刷新" />
      </div>
    </div>
    <el-alert
      v-if="rateLimitMessage"
      class="mb16"
      type="warning"
      show-icon
      :closable="false"
      :title="rateLimitMessage"
    />

    <!-- 大盘指数条：仅在盘中显示在盘市场，不开盘整体隐藏 -->
    <market-index-strip ref="indexStripRef" />

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :sm="8">
        <div class="stat-card stat-blue">
          <div class="stat-icon"><el-icon><Document /></el-icon></div>
          <div class="stat-info">
            <div class="stat-label">总资讯数</div>
            <div class="stat-value">{{ stats.total ?? 0 }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="stat-card stat-purple">
          <div class="stat-icon"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-info">
            <div class="stat-label">今日新增</div>
            <div class="stat-value">{{ stats.today ?? 0 }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="8">
        <div class="stat-card stat-orange">
          <div class="stat-icon"><el-icon><Clock /></el-icon></div>
          <div class="stat-info">
            <div class="stat-label">待分析数</div>
            <div class="stat-value">{{ stats.unanalyzed ?? 0 }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 市场影响卡片 -->
    <el-row :gutter="16" class="mb16">
      <el-col :xs="24" :md="8" v-for="market in markets" :key="market.key">
        <div class="market-card" :class="directionClass(market.direction)">
          <div class="market-head">
            <span class="market-name">{{ market.name }}</span>
            <el-tag :color="directionColor(market.direction)" effect="dark" class="direction-tag" v-if="market.direction">
              {{ directionLabel(market.direction) }}
            </el-tag>
            <el-tag type="info" v-else>暂无</el-tag>
          </div>
          <div class="market-score" :style="{ color: directionColor(market.direction) }">
            {{ market.score !== null && market.score !== undefined ? market.score : '--' }}
            <span class="score-unit">分</span>
          </div>
          <div class="market-reason" :title="market.reason">{{ market.reason || '暂无分析理由' }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card shadow="never" class="panel-card mb16">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">市场情绪分数趋势</span>
          <span class="panel-sub">最近 24 次分析</span>
        </div>
      </template>
      <div ref="trendRef" class="trend-chart"></div>
    </el-card>

    <!-- 最新分析摘要与风险事件 -->
    <el-row :gutter="16">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-header"><span class="panel-title">最新分析摘要</span></div>
          </template>
          <div class="summary-text" v-if="latest.summary">{{ latest.summary }}</div>
          <el-empty v-else description="暂无分析数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-header"><span class="panel-title">风险事件</span></div>
          </template>
          <template v-if="riskEventList.length > 0">
            <div class="risk-item" v-for="(item, index) in riskEventList" :key="index">
              <el-icon class="risk-icon"><Warning /></el-icon>
              <span>{{ item }}</span>
            </div>
          </template>
          <el-empty v-else description="暂无风险事件" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="SentimentDashboard">
import { applyChartTheme } from '@/utils/echartsTheme';
import { useEChart } from '@/composables/useEChart';
import { getStats, getTrend, listAnalysis, collectNews, runAnalysis } from '@/api/sentiment';
import { sentimentIndexTo100 } from '@/utils/sentimentScore';
import { formatBeijingTime, formatBeijingTimeShort } from '@/utils/beijingTime';

const { proxy } = getCurrentInstance();

const indexStripRef = ref(null);

const stats = ref({});
const latest = ref({});
const trendRef = ref(null);
const { setOption: setTrendOption, dispose: disposeTrend } = useEChart(trendRef);
const collectLoading = ref(false);
const analyzeLoading = ref(false);
const rateLimitedUntil = ref(0);
const retryLeft = ref(0);
const rateLimitMessage = ref('');
let retryTimer = null;

/** 只展示可读时间，避免把整条 analysis 对象渲染成 JSON */
const latestAnalysisTime = computed(() => {
  const fromLatest = latest.value?.createTime;
  const la = stats.value?.latestAnalysis;
  const fromStats = la && typeof la === 'object' ? la.createTime : (typeof la === 'string' ? la : '');
  const raw = fromLatest || fromStats;
  if (!raw) return '';
  return formatBeijingTime(raw);
});

const markets = computed(() => [
  { key: 'us', name: '美股三大指数', direction: latest.value.usDirection, score: sentimentIndexTo100(latest.value.usScore), reason: latest.value.usReason },
  { key: 'hk', name: '港股指数', direction: latest.value.hkDirection, score: sentimentIndexTo100(latest.value.hkScore), reason: latest.value.hkReason },
  { key: 'a', name: 'A股指数', direction: latest.value.aDirection, score: sentimentIndexTo100(latest.value.aScore), reason: latest.value.aReason }
]);

const riskEventList = computed(() => {
  const raw = latest.value.riskEvents;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map(item => (typeof item === 'string' ? item : JSON.stringify(item)));
  } catch {
    /* 非JSON字符串，按分隔符切分 */
  }
  return String(raw).split(/[\n;；]/).map(s => s.trim()).filter(s => s);
});

/** 方向归一化：利多/bullish/up -> up; 利空/bearish/down -> down; 其他 -> flat */
function normalizeDirection(direction) {
  if (!direction) return '';
  const d = String(direction).toLowerCase();
  if (d.includes('多') || d.includes('bull') || d.includes('up') || d.includes('涨') || d.includes('positive')) return 'up';
  if (d.includes('空') || d.includes('bear') || d.includes('down') || d.includes('跌') || d.includes('negative')) return 'down';
  return 'flat';
}

/** 利多红涨、利空绿跌（中国习惯）、中性灰 */
function directionColor(direction) {
  const d = normalizeDirection(direction);
  if (d === 'up') return '#f56c6c';
  if (d === 'down') return '#67c23a';
  return '#909399';
}

function directionLabel(direction) {
  const d = normalizeDirection(direction);
  if (d === 'up') return '利多';
  if (d === 'down') return '利空';
  return direction ? '中性' : '';
}

function directionClass(direction) {
  const d = normalizeDirection(direction);
  if (d === 'up') return 'market-up';
  if (d === 'down') return 'market-down';
  return 'market-flat';
}

/** 查询统计数据 */
function getStatsData() {
  getStats().then(response => {
    const data = response.data || {};
    stats.value = data;
    // stats 自带最新分析对象时同步到 latest，避免标题时间与下方卡片不一致
    if (data.latestAnalysis && typeof data.latestAnalysis === 'object') {
      latest.value = { ...latest.value, ...data.latestAnalysis };
    }
  });
}

/** 查询最新一次分析结果 */
function getLatestAnalysis() {
  listAnalysis({ pageNum: 1, pageSize: 1, status: '0' }).then(response => {
    if (response.rows && response.rows[0]) {
      latest.value = response.rows[0];
    }
  });
}

/** 查询趋势并渲染图表 */
function getTrendData() {
  getTrend(24).then(response => {
    const list = response.data || [];
    renderTrend(list);
  });
}

function renderTrend(list) {
  if (!trendRef.value) return;
  const times = list.map(item => formatBeijingTimeShort(item.createTime));
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['美股', '港股', 'A股'], top: 0 },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: times,
      axisLabel: {
        formatter: value => (value ? String(value).slice(5, 16) : value)
      }
    },
    yAxis: { type: 'value', name: '分数', min: 0, max: 100 },
    series: [
      { name: '美股', type: 'line', smooth: true, data: list.map(item => sentimentIndexTo100(item.usScore)), itemStyle: { color: '#409eff' }, areaStyle: { opacity: 0.08 } },
      { name: '港股', type: 'line', smooth: true, data: list.map(item => sentimentIndexTo100(item.hkScore)), itemStyle: { color: '#e6a23c' }, areaStyle: { opacity: 0.08 } },
      { name: 'A股', type: 'line', smooth: true, data: list.map(item => sentimentIndexTo100(item.aScore)), itemStyle: { color: '#f56c6c' }, areaStyle: { opacity: 0.08 } }
    ]
  };
  setTrendOption(applyChartTheme(option));
}

/** 立即采集 */
function handleCollect() {
  collectLoading.value = true;
  collectNews().then((res) => {
    const d = (res && res.data) || {};
    proxy.$modal.msgSuccess((res && res.msg) || (d.accepted ? '已加入后台队列' : '采集任务已触发'));
    if (!d.accepted) refreshAll();
  }).finally(() => {
    collectLoading.value = false;
  });
}

function startRateLimitCooldown(seconds, message) {
  const wait = Math.max(15, Math.min(Number(seconds) || 60, 300));
  rateLimitedUntil.value = Date.now() + wait * 1000;
  rateLimitMessage.value = message || 'AI 分析触发限流，请稍后再试，不要连续点击';
  retryLeft.value = wait;
  if (retryTimer) clearInterval(retryTimer);
  retryTimer = setInterval(() => {
    const left = Math.ceil((rateLimitedUntil.value - Date.now()) / 1000);
    retryLeft.value = Math.max(0, left);
    if (left <= 0) {
      clearInterval(retryTimer);
      retryTimer = null;
      rateLimitedUntil.value = 0;
      rateLimitMessage.value = '';
    }
  }, 1000);
}

/** 立即分析 */
function handleAnalyze() {
  if (rateLimitedUntil.value && Date.now() < rateLimitedUntil.value) {
    return;
  }
  analyzeLoading.value = true;
  runAnalysis().then((res) => {
    const data = res.data || {};
    if (data.rateLimited || data.code === 429) {
      startRateLimitCooldown(data.retryAfter, data.message);
      return;
    }
    const msg = data.message || res.msg || '';
    if (msg.includes('限流') || msg.includes('过于频繁')) {
      startRateLimitCooldown(60, msg);
      return;
    }
    proxy.$modal.msgSuccess(res.msg || data.message || (data.accepted ? '已加入后台队列' : 'AI分析任务已触发'));
    if (!data.accepted) refreshAll();
  }).catch((err) => {
    const text = String(err && err.message ? err.message : err || '');
    if (text.includes('429') || text.includes('限流') || text.includes('过于频繁')) {
      startRateLimitCooldown(60, 'AI 分析触发限流，请稍后再试，不要连续点击');
      return;
    }
  }).finally(() => {
    analyzeLoading.value = false;
  });
}

/** 刷新全部数据 */
function refreshAll() {
  getStatsData();
  getLatestAnalysis();
  getTrendData();
  indexStripRef.value && indexStripRef.value.loadQuotes();
}

onMounted(() => {
  refreshAll();
});

onBeforeUnmount(() => {
  if (retryTimer) {
    clearInterval(retryTimer);
    retryTimer = null;
  }
  disposeTrend();
});
</script>

<style lang="scss" scoped>
.sentiment-dashboard {
  .mb16 {
    margin-bottom: 16px;
  }
  .dash-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 8px;
    .title-text {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-emphasis, #303133);
    }
    .title-sub {
      margin-left: 12px;
      font-size: 13px;
      color: #909399;
    }
  }
  .stat-card {
    display: flex;
    align-items: center;
    border-radius: 14px;
    padding: 20px 24px;
    color: #fff;
    margin-bottom: 8px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
    .stat-icon {
      width: 52px;
      height: 52px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.22);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      margin-right: 16px;
    }
    .stat-label {
      font-size: 13px;
      opacity: 0.9;
    }
    .stat-value {
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
    }
  }
  .stat-blue {
    background: linear-gradient(135deg, #409eff 0%, #2d6cdf 100%);
  }
  .stat-purple {
    background: linear-gradient(135deg, #9254de 0%, #6a3fd0 100%);
  }
  .stat-orange {
    background: linear-gradient(135deg, #f0a020 0%, #e0701a 100%);
  }
  .market-card {
    background: var(--surface-card, #fff);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 8px;
    border: 1px solid var(--border-soft, #ebeef5);
    border-top: 4px solid #909399;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
    min-height: 150px;
    &.market-up {
      border-top-color: #f56c6c;
      background: linear-gradient(180deg, rgba(245, 108, 108, 0.12) 0%, var(--surface-card, #fff) 55%);
    }
    &.market-down {
      border-top-color: #67c23a;
      background: linear-gradient(180deg, rgba(103, 194, 58, 0.12) 0%, var(--surface-card, #fff) 55%);
    }
    .market-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      .market-name {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-emphasis, #303133);
      }
      .direction-tag {
        border: none;
        color: #fff;
      }
    }
    .market-score {
      font-size: 36px;
      font-weight: 700;
      margin: 8px 0 4px;
      .score-unit {
        font-size: 14px;
        font-weight: 400;
        color: #909399;
      }
    }
    .market-reason {
      font-size: 13px;
      color: var(--text-secondary, #606266);
      line-height: 1.6;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }
  .panel-card {
    border-radius: 14px;
    .panel-header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
    }
    .panel-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-emphasis, #303133);
    }
    .panel-sub {
      font-size: 12px;
      color: #909399;
    }
  }
  .trend-chart {
    width: 100%;
    height: 340px;
  }
  .summary-text {
    font-size: 14px;
    color: var(--text-emphasis, #303133);
    line-height: 1.9;
    white-space: pre-wrap;
    min-height: 120px;
  }
  .risk-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    background: #fdf6ec;
    color: #b88230;
    font-size: 13px;
    line-height: 1.6;
    margin-bottom: 8px;
    .risk-icon {
      margin-top: 3px;
      color: #e6a23c;
      flex-shrink: 0;
    }
  }
}
</style>
