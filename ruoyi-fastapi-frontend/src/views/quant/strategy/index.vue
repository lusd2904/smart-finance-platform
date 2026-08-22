<template>
  <div class="app-container quant-strategy">
    <!-- 策略运行区 -->
    <el-card shadow="never" class="panel-card mb16">
      <template #header>
        <div class="panel-header"><span class="panel-title">策略信号运行</span></div>
      </template>
      <div class="run-bar">
        <div class="run-item">
          <span class="run-label">策略档位</span>
          <el-radio-group v-model="profile">
            <el-radio-button label="conservative">保守型</el-radio-button>
            <el-radio-button label="balanced">均衡型</el-radio-button>
            <el-radio-button label="aggressive">激进型</el-radio-button>
          </el-radio-group>
        </div>
        <div class="run-item">
          <span class="run-label">标的范围</span>
          <el-select v-model="selectedSymbols" multiple collapse-tags collapse-tags-tooltip filterable placeholder="留空则全市场" style="width: 320px">
            <el-option v-for="it in instruments" :key="it.symbol + it.market" :label="`${it.name} (${it.symbol})`" :value="it.symbol" />
          </el-select>
        </div>
        <el-button type="primary" icon="VideoPlay" :loading="runLoading" @click="handleRun" v-hasPermi="['quant:strategy:run']">运行策略</el-button>
      </div>

      <el-table v-if="signals.length > 0" :data="signals" style="width: 100%" class="mb8">
        <el-table-column label="标的" prop="symbol" width="140" />
        <el-table-column label="信号" prop="signal" width="110" align="center">
          <template #default="scope">
            <el-tag :type="signalTagType(scope.row.signal)" effect="dark">{{ signalLabel(scope.row.signal) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评分" prop="score" width="120" align="center">
          <template #default="scope">
            <span :style="{ color: signalColor(scope.row.signal), fontWeight: 600 }">{{ scope.row.score ?? '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" prop="confidence" width="140" align="center">
          <template #default="scope">
            <el-progress :percentage="confPct(scope.row.confidence)" :stroke-width="10" :color="signalColor(scope.row.signal)" />
          </template>
        </el-table-column>
        <el-table-column label="理由" prop="reason" :show-overflow-tooltip="true" />
      </el-table>
      <el-empty v-else-if="!runLoading" description="选择档位后运行策略生成信号" :image-size="80" />
    </el-card>

    <!-- 历史运行记录 -->
    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="panel-header">
          <span class="panel-title">历史运行记录</span>
          <el-button size="small" icon="Refresh" text @click="getHistory">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="historyLoading" :data="historyList" style="width: 100%">
        <el-table-column label="编号" prop="id" width="80" align="center" />
        <el-table-column label="运行时间" prop="createTime" width="180" align="center">
          <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="档位" prop="profile" width="120" align="center">
          <template #default="scope">{{ profileLabel(scope.row.profile) }}</template>
        </el-table-column>
        <el-table-column label="标的" prop="symbol" width="140" />
        <el-table-column label="信号" prop="signal" width="110" align="center">
          <template #default="scope">
            <el-tag :type="signalTagType(scope.row.signal)" effect="dark">{{ signalLabel(scope.row.signal) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评分" prop="score" width="90" align="center" />
        <el-table-column label="理由" prop="reason" :show-overflow-tooltip="true" />
      </el-table>
      <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getHistory"
      />
    </el-card>
  </div>
</template>

<script setup name="QuantStrategy">
import { runStrategy, listStrategyHistory } from '@/api/quant';
import { listInstrument } from '@/api/market';

const { proxy } = getCurrentInstance();

const PROFILE_MAP = { conservative: '保守型', balanced: '均衡型', aggressive: '激进型' };

const profile = ref('balanced');
const instruments = ref([]);
const selectedSymbols = ref([]);
const signals = ref([]);
const runLoading = ref(false);

const historyList = ref([]);
const historyLoading = ref(false);
const total = ref(0);
const queryParams = ref({ pageNum: 1, pageSize: 10 });

function profileLabel(p) { return PROFILE_MAP[p] || p || '--'; }

/** 信号归一化 */
function normalizeSignal(signal) {
  if (!signal) return 'hold';
  const s = String(signal).toUpperCase();
  if (s.includes('BUY') || s.includes('买') || s.includes('多')) return 'buy';
  if (s.includes('SELL') || s.includes('卖') || s.includes('空')) return 'sell';
  return 'hold';
}
function signalLabel(signal) {
  const s = normalizeSignal(signal);
  return { buy: 'BUY', sell: 'SELL', hold: 'HOLD' }[s];
}
function signalTagType(signal) {
  const s = normalizeSignal(signal);
  return { buy: 'success', sell: 'danger', hold: 'info' }[s];
}
function signalColor(signal) {
  const s = normalizeSignal(signal);
  return { buy: '#67c23a', sell: '#f56c6c', hold: '#909399' }[s];
}
function confPct(conf) {
  if (conf == null) return 0;
  let n = Number(conf);
  if (isNaN(n)) return 0;
  if (n <= 1) n = n * 100;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function loadInstruments() {
  listInstrument().then(response => {
    instruments.value = response.data || response.rows || [];
  });
}

/** 运行策略 */
function handleRun() {
  runLoading.value = true;
  const body = { profile: profile.value };
  if (selectedSymbols.value.length > 0) body.symbols = selectedSymbols.value;
  runStrategy(body).then(response => {
    const d = response.data || {};
    if (d.accepted || d.jobId) {
      proxy.$modal.msgSuccess(response.msg || '已加入后台队列，稍后在策略历史中查看');
      getHistory();
      return;
    }
    signals.value = d.signals || (Array.isArray(d) ? d : response.rows) || [];
    proxy.$modal.msgSuccess(`策略运行完成，生成 ${signals.value.length} 条信号`);
    getHistory();
  }).finally(() => {
    runLoading.value = false;
  });
}

/** 查询历史 */
function getHistory() {
  historyLoading.value = true;
  listStrategyHistory(queryParams.value).then(response => {
    historyList.value = response.rows || [];
    total.value = response.total || 0;
    historyLoading.value = false;
  }).catch(() => {
    historyLoading.value = false;
  });
}

onMounted(() => {
  loadInstruments();
  getHistory();
});
</script>

<style lang="scss" scoped>
.quant-strategy {
  .mb16 { margin-bottom: 16px; }
  .mb8 { margin-bottom: 8px; }
  .panel-card {
    border-radius: 14px;
    .panel-header {
      display: flex; align-items: center; justify-content: space-between;
      .panel-title { font-size: 15px; font-weight: 600; color: var(--text-emphasis, #303133); }
    }
  }
  .run-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 20px;
    margin-bottom: 16px;
    .run-item { display: flex; align-items: center; gap: 10px; }
    .run-label { font-size: 13px; color: #606266; font-weight: 600; }
  }
}
</style>
