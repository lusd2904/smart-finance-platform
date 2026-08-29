<template>
  <div class="app-container quant-factor">
    <el-row :gutter="16">
      <!-- 因子族体系 -->
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="panel-card" v-loading="schemaLoading">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">多因子族体系</span>
              <span class="panel-sub">{{ factorFamilies.length }} 个因子族</span>
            </div>
          </template>
          <el-collapse v-model="activeFamilies">
            <el-collapse-item v-for="(fam, idx) in factorFamilies" :key="fam.key || idx" :name="String(fam.key || idx)">
              <template #title>
                <span class="fam-title">
                  <el-tag :color="famColor(idx)" effect="dark" style="border:none;color:#fff;margin-right:8px">{{ idx + 1 }}</el-tag>
                  {{ fam.name || fam.label }}
                </span>
              </template>
              <div class="fam-desc" v-if="fam.desc || fam.description">{{ fam.desc || fam.description }}</div>
              <div class="fam-factors">
                <el-tag v-for="(f, i) in normalizeFactors(fam)" :key="i" class="factor-chip" effect="plain">{{ f }}</el-tag>
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-if="factorFamilies.length === 0 && !schemaLoading" description="暂无因子定义" :image-size="70" />
        </el-card>
      </el-col>

      <!-- 因子计算 -->
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">因子计算与打分</span>
            </div>
          </template>
          <div class="compute-bar">
            <el-select v-model="selectedSymbol" placeholder="选择标的" filterable style="width: 240px" @change="onSymbolChange">
              <el-option v-for="it in instruments" :key="it.symbol + it.market" :label="`${it.name} (${it.symbol})`" :value="it.symbol + '|' + it.market" />
            </el-select>
            <el-button type="primary" icon="MagicStick" :loading="computeLoading" :disabled="!selectedSymbol" @click="handleCompute" v-hasPermi="['quant:factor:compute']">计算因子</el-button>
            <el-button :loading="scanLoading" @click="handleScan" v-hasPermi="['quant:strategy:run']">全市场日扫</el-button>
            <el-button icon="Download" @click="handleExport" v-hasPermi="['quant:factor:list']">导出快照</el-button>
          </div>
          <div v-if="snapshotHint" class="snap-hint">{{ snapshotHint }}</div>

          <div v-if="computeResult">
            <div class="score-banner">
              <div class="score-label">综合打分</div>
              <div class="score-num" :style="{ color: scoreColor(totalScore) }">{{ totalScore }}</div>
              <div class="score-tag">
                <el-tag :color="scoreColor(totalScore)" effect="dark" style="border:none;color:#fff">{{ scoreLevel(totalScore) }}</el-tag>
              </div>
            </div>
            <div ref="radarRef" class="radar-chart"></div>
            <el-table :data="factorRows" style="width: 100%" size="small" max-height="300">
              <el-table-column label="因子族" prop="name" />
              <el-table-column label="因子值" prop="value" width="140" align="center">
                <template #default="scope">{{ formatValue(scope.row.value) }}</template>
              </el-table-column>
              <el-table-column label="得分" prop="score" width="120" align="center">
                <template #default="scope">
                  <span :style="{ color: scoreColor(scope.row.score), fontWeight: 600 }">{{ scope.row.score ?? '--' }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="alphaRows.length" class="alpha-block">
              <div class="alpha-title">
                高阶因子
                <el-tag size="small" effect="plain">Alpha101 {{ alpha101Count }}</el-tag>
                <el-tag size="small" effect="plain">Alpha158 {{ alpha158Count }}</el-tag>
              </div>
              <el-table :data="alphaRows" size="small" max-height="240">
                <el-table-column prop="key" label="因子" min-width="120" />
                <el-table-column label="值" width="140" align="right">
                  <template #default="scope">{{ formatValue(scope.row.value) }}</template>
                </el-table-column>
              </el-table>
              <div v-if="alphaCsRows.length" class="alpha-title" style="margin-top:12px">
                截面 rank
                <el-tag size="small" effect="plain">Alpha101 CS {{ alphaCsRows.length }}</el-tag>
              </div>
              <el-table v-if="alphaCsRows.length" :data="alphaCsRows" size="small" max-height="200">
                <el-table-column prop="key" label="因子" min-width="120" />
                <el-table-column label="百分位" width="140" align="right">
                  <template #default="scope">{{ formatValue(scope.row.value) }}</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
          <el-empty v-else description="选择标的后计算因子" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card qc-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">因子质检（Alphalens 风格）</span>
          <div class="qc-actions">
            <span class="panel-sub">{{ qcHint || '截面 Spearman IC / IR / 五分位收益' }}</span>
            <el-button type="primary" plain :loading="qcLoading" @click="handleQc" v-hasPermi="['quant:factor:compute']">运行质检</el-button>
          </div>
        </div>
      </template>
      <el-table :data="qcRows" size="small" v-loading="qcLoading">
        <el-table-column prop="factorLabel" label="因子" min-width="140" />
        <el-table-column prop="horizon" label="周期" width="70" align="center">
          <template #default="scope">{{ scope.row.horizon }}D</template>
        </el-table-column>
        <el-table-column label="IC" width="90" align="right">
          <template #default="scope">{{ formatValue(scope.row.icMean) }}</template>
        </el-table-column>
        <el-table-column label="IR" width="90" align="right">
          <template #default="scope">{{ formatValue(scope.row.ir) }}</template>
        </el-table-column>
        <el-table-column label="IC>0占比" width="100" align="right">
          <template #default="scope">{{ formatPct(scope.row.icPositiveRatio) }}</template>
        </el-table-column>
        <el-table-column label="Q1" width="80" align="right">
          <template #default="scope">{{ formatValue(scope.row.quantiles && scope.row.quantiles.q1) }}</template>
        </el-table-column>
        <el-table-column label="Q5" width="80" align="right">
          <template #default="scope">{{ formatValue(scope.row.quantiles && scope.row.quantiles.q5) }}</template>
        </el-table-column>
        <el-table-column label="多空价差" width="90" align="right">
          <template #default="scope">{{ formatValue(scope.row.spread) }}</template>
        </el-table-column>
        <el-table-column prop="sampleDates" label="样本日" width="80" align="center" />
      </el-table>
      <el-empty v-if="!qcRows.length && !qcLoading" description="尚未运行质检，点击右上角生成 IC/IR 报告" :image-size="70" />
    </el-card>
  </div>
</template>

<script setup name="QuantFactor">
import { useEChart } from '@/composables/useEChart';
import { getFactorSchema, computeFactor, listFactorSnapshots, runDailyFactorScan, getReadmodelOverview, getFactorQc, runFactorQc } from '@/api/quant';
import { listInstrument } from '@/api/market';

const { proxy } = getCurrentInstance();

const FAM_COLORS = ['#6366f1', '#409eff', '#13c2c2', '#f0a020', '#9254de', '#f56c6c', '#67c23a'];

const factorFamilies = ref([]);
const schemaLoading = ref(false);
const activeFamilies = ref([]);
const instruments = ref([]);
const selectedSymbol = ref('');
const computeResult = ref(null);
const computeLoading = ref(false);
const scanLoading = ref(false);
const snapshotHint = ref('');
const qcRows = ref([]);
const qcHint = ref('');
const qcLoading = ref(false);

const radarRef = ref(null);
const { setOption: setRadarOption, dispose: disposeRadar } = useEChart(radarRef);

function famColor(idx) { return FAM_COLORS[idx % FAM_COLORS.length]; }

/** 归一化因子列表 */
function normalizeFactors(fam) {
  const raw = fam.inputs || fam.factors || fam.items || fam.metrics || [];
  if (Array.isArray(raw)) {
    return raw.map(f => (typeof f === 'string' ? f : (f.name || f.label || JSON.stringify(f))));
  }
  return [];
}

/** 因子行（表格 + 雷达）——对齐后端 data.score(各族分) + data.metrics(因子值) */
const FAMILY_LABELS = {
  trend: '趋势因子', priceAction: '价型因子', momentum: '动量因子', breakout: '突破因子',
  volumeFlow: '量能资金', reversion: '回归因子', volatility: '波动因子', liquidity: '流动性',
};
const factorRows = computed(() => {
  const res = computeResult.value;
  if (!res) return [];
  // 优先：后端 score 对象（含 total + 8 大族分）
  const score = res.score;
  if (score && typeof score === 'object') {
    const famKeys = (factorFamilies.value.length ? factorFamilies.value.map(f => f.key) : Object.keys(FAMILY_LABELS));
    return famKeys
      .filter(k => score[k] != null)
      .map(k => ({ name: FAMILY_LABELS[k] || k, value: score[k], score: score[k] }));
  }
  // 兼容旧结构
  const factors = res.factors || res.families || [];
  if (Array.isArray(factors)) {
    return factors.map(f => ({ name: f.name || f.label || f.key, value: f.value, score: f.score }));
  }
  return Object.keys(factors).map(k => {
    const v = factors[k];
    if (v && typeof v === 'object') return { name: k, value: v.value, score: v.score };
    return { name: k, value: v, score: v };
  });
});

const alpha101Count = computed(() => Number(computeResult.value?.metrics?.alpha101Count || 0));
const alpha158Count = computed(() => Number(computeResult.value?.metrics?.alpha158Count || 0));
const alphaRows = computed(() => {
  const metrics = computeResult.value?.metrics || {};
  const a101 = metrics.alpha101 || {};
  const a158 = metrics.alpha158 || {};
  const rows = [
    ...Object.keys(a101).map(k => ({ key: k, value: a101[k] })),
    ...Object.keys(a158).slice(0, 24).map(k => ({ key: k, value: a158[k] })),
  ];
  return rows.filter(r => r.value != null).slice(0, 30);
});
const alphaCsRows = computed(() => {
  const cs = computeResult.value?.alphaCs || computeResult.value?.metrics?.alphaCs || {};
  return Object.keys(cs).map(k => ({ key: k, value: cs[k] }));
});

const totalScore = computed(() => {
  const res = computeResult.value;
  if (!res) return '--';
  const s = (res.score && typeof res.score === 'object' ? res.score.total : undefined)
    ?? res.totalScore ?? res.total ?? (typeof res.score === 'number' ? res.score : undefined);
  return s != null ? s : '--';
});

function formatValue(v) {
  if (v == null) return '--';
  if (typeof v === 'number') return Number(v.toFixed(4));
  return v;
}

function formatPct(v) {
  if (v == null || v === '') return '--';
  const n = Number(v);
  if (Number.isNaN(n)) return '--';
  return (n * 100).toFixed(1) + '%';
}

function applyQcPayload(payload) {
  const data = payload || {};
  qcRows.value = data.items || [];
  const asOf = data.asOf ? `截至 ${data.asOf}` : '';
  const count = data.symbolCount ? `${data.symbolCount} 只标的` : '';
  qcHint.value = [data.message, asOf, count].filter(Boolean).join(' · ');
}

function loadQc() {
  getFactorQc('US').then(res => applyQcPayload(res.data)).catch(() => {});
}

async function handleQc() {
  qcLoading.value = true;
  try {
    const res = await runFactorQc('US');
    const jobId = res.data && res.data.jobId;
    if (jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队');
      const { pollMarketJob } = await import('@/api/market');
      const ticket = await pollMarketJob(jobId);
      if (ticket.status === 'failed') {
        proxy.$modal.msgError(ticket.error || '质检失败');
        return;
      }
    } else if (res.data && res.data.items) {
      applyQcPayload(res.data);
    }
    loadQc();
    proxy.$modal.msgSuccess(res.msg || '质检完成');
  } finally {
    qcLoading.value = false;
  }
}

function scoreColor(score) {
  const s = Number(score);
  if (isNaN(s)) return '#909399';
  if (s >= 70) return '#f56c6c';
  if (s >= 40) return '#e6a23c';
  return '#67c23a';
}
function scoreLevel(score) {
  const s = Number(score);
  if (isNaN(s)) return '未知';
  if (s >= 70) return '强';
  if (s >= 40) return '中性';
  return '弱';
}

/** 加载因子族定义 */
function loadSchema() {
  schemaLoading.value = true;
  getFactorSchema().then(response => {
    const data = response.data || {};
    // 后端结构：data.families = [{key,label,inputs,desc}, ...]
    let fams = data.families || data.factorFamilies || [];
    if (!Array.isArray(fams)) {
      fams = Object.keys(fams).map(k => ({ key: k, ...(typeof fams[k] === 'object' ? fams[k] : { inputs: fams[k] }) }));
    }
    factorFamilies.value = fams;
    activeFamilies.value = fams.map((f, i) => String(f.key || i));
    schemaLoading.value = false;
  }).catch(() => {
    schemaLoading.value = false;
  });
}

function loadInstruments() {
  listInstrument().then(response => {
    instruments.value = response.data || response.rows || [];
  });
}

function loadSnapshots() {
  Promise.allSettled([listFactorSnapshots(12), getReadmodelOverview()]).then(([snapRes, overviewRes]) => {
    const snaps = snapRes.status === 'fulfilled' ? (snapRes.value.data || []) : [];
    const overview = overviewRes.status === 'fulfilled' ? (overviewRes.value.data || {}) : {};
    const asOf = overview.factorScan?.asOf || overview.refreshTime;
    const source = overview.source === 'scheduled' ? '定时快照' : '实时';
    if (snaps.length) {
      snapshotHint.value = `${source} · 已落库 ${snaps.length} 个标的` + (asOf ? ` · ${asOf}` : '');
    } else if (asOf) {
      snapshotHint.value = `${source} · ${asOf}`;
    }
  });
}

function handleExport() {
  proxy.download.zip('/quant/factor/snapshots/export', 'factor_snapshots.csv')
}

async function handleScan() {
  scanLoading.value = true;
  try {
    const res = await runDailyFactorScan('balanced');
    const jobId = res.data && res.data.jobId;
    if (jobId) {
      proxy.$modal.msgSuccess(res.msg || '已入队');
      const { pollMarketJob } = await import('@/api/market');
      const ticket = await pollMarketJob(jobId);
      if (ticket.status === 'failed') {
        proxy.$modal.msgError(ticket.error || '日扫失败');
        return;
      }
    }
    proxy.$modal.msgSuccess(res.msg || '日扫完成');
    loadSnapshots();
  } finally {
    scanLoading.value = false;
  }
}

function onSymbolChange() {
  computeResult.value = null;
}

/** 计算因子 */
function handleCompute() {
  if (!selectedSymbol.value) return;
  const [symbol, market] = selectedSymbol.value.split('|');
  computeLoading.value = true;
  computeFactor({ symbol, market }).then(response => {
    computeResult.value = response.data || {};
    nextTick(renderRadar);
  }).finally(() => {
    computeLoading.value = false;
  });
}

/** 渲染雷达图 */
function renderRadar() {
  if (!radarRef.value) return;
  const rows = factorRows.value;
  const indicator = rows.map(r => ({ name: r.name, max: 100 }));
  const values = rows.map(r => (r.score != null ? Number(r.score) : 0));
  setRadarOption({
    tooltip: {},
    radar: {
      indicator,
      radius: '65%',
      splitNumber: 4,
      axisName: { color: '#606266', fontSize: 12 },
      splitArea: { areaStyle: { color: ['#fafbff', '#f0f2f8'] } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '因子得分',
        areaStyle: { color: 'rgba(99,102,241,0.25)' },
        lineStyle: { color: '#6366f1' },
        itemStyle: { color: '#6366f1' }
      }]
    }]
  }, true);
}

onMounted(() => {
  loadSchema();
  loadInstruments();
  loadSnapshots();
  loadQc();
});

onBeforeUnmount(() => {
  disposeRadar();
});
</script>

<style lang="scss" scoped>
.quant-factor {
  .panel-card {
    border-radius: 14px;
    margin-bottom: 8px;
    .panel-header {
      display: flex; align-items: baseline; justify-content: space-between;
      .panel-title { font-size: 15px; font-weight: 600; color: var(--text-emphasis, #303133); }
      .panel-sub { font-size: 12px; color: #909399; }
    }
  }
  .fam-title { display: flex; align-items: center; font-size: 14px; font-weight: 600; color: var(--text-emphasis, #303133); }
  .fam-desc { font-size: 13px; color: #606266; line-height: 1.7; margin-bottom: 8px; }
  .fam-factors { display: flex; flex-wrap: wrap; gap: 6px; }
  .factor-chip { margin: 0; }
  .compute-bar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
  .score-banner {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 20px;
    border-radius: 12px;
    background: linear-gradient(135deg, #eef0ff 0%, #f7f8ff 100%);
    margin-bottom: 12px;
    .score-label { font-size: 14px; color: #606266; font-weight: 600; }
    .score-num { font-size: 40px; font-weight: 700; line-height: 1; }
  }
  .radar-chart { width: 100%; height: 340px; margin-bottom: 12px; }
  .snap-hint { font-size: 12px; color: var(--text-muted, #909399); margin: -8px 0 12px; }
  .alpha-block { margin-top: 12px; }
  .alpha-title { display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 8px; color: var(--text-emphasis, #303133); }
  .qc-card { margin-top: 16px; }
  .qc-actions { display: flex; align-items: center; gap: 12px; }
}
</style>
