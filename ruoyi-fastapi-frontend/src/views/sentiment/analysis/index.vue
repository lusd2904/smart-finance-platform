<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="分析状态" clearable style="width: 140px">
          <el-option label="成功" value="0" />
          <el-option label="失败" value="1" />
        </el-select>
      </el-form-item>
      <el-form-item label="分析时间" style="width: 308px">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD HH:mm:ss"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :default-time="[new Date(2000, 1, 1, 0, 0, 0), new Date(2000, 1, 1, 23, 59, 59)]"
        ></el-date-picker>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="MagicStick"
          :loading="analyzeLoading"
          @click="handleAnalyze"
          v-hasPermi="['sentiment:analysis:run']"
        >手动分析</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="analysisList" @row-click="handleRowClick" style="cursor: pointer">
      <el-table-column label="编号" align="center" prop="analysisId" width="80" />
      <el-table-column label="分析时间" align="center" prop="createTime" width="170">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="资讯条数" align="center" prop="newsCount" width="90" />
      <el-table-column label="美股" align="center" width="120">
        <template #default="scope">
          <el-tag v-if="scope.row.usDirection" :color="directionColor(scope.row.usDirection)" effect="dark" class="direction-tag">
            {{ directionLabel(scope.row.usDirection) }} {{ scope.row.usScore }}
          </el-tag>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column label="港股" align="center" width="120">
        <template #default="scope">
          <el-tag v-if="scope.row.hkDirection" :color="directionColor(scope.row.hkDirection)" effect="dark" class="direction-tag">
            {{ directionLabel(scope.row.hkDirection) }} {{ scope.row.hkScore }}
          </el-tag>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column label="A股" align="center" width="120">
        <template #default="scope">
          <el-tag v-if="scope.row.aDirection" :color="directionColor(scope.row.aDirection)" effect="dark" class="direction-tag">
            {{ directionLabel(scope.row.aDirection) }} {{ scope.row.aScore }}
          </el-tag>
          <span v-else>--</span>
        </template>
      </el-table-column>
      <el-table-column label="摘要" align="left" prop="summary" :show-overflow-tooltip="true" />
      <el-table-column label="模型" align="center" prop="modelName" width="150" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" prop="status" width="90">
        <template #default="scope">
          <el-tag :type="String(scope.row.status) === '0' ? 'success' : 'danger'">
            {{ String(scope.row.status) === '0' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="90" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click.stop="handleDetail(scope.row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 分析详情对话框 -->
    <el-dialog title="分析详情" v-model="open" width="820px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="分析时间">{{ parseTime(detail.createTime) }}</el-descriptions-item>
        <el-descriptions-item label="资讯条数">{{ detail.newsCount }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ detail.modelName }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="String(detail.status) === '0' ? 'success' : 'danger'">
            {{ String(detail.status) === '0' ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div class="detail-section" v-if="detail.summary">
        <div class="section-title">分析摘要</div>
        <div class="section-body">{{ detail.summary }}</div>
      </div>

      <div class="detail-section">
        <div class="section-title">市场影响</div>
        <div class="market-block" v-for="market in detailMarkets" :key="market.name">
          <div class="market-line">
            <span class="market-name">{{ market.name }}</span>
            <el-tag v-if="market.direction" :color="directionColor(market.direction)" effect="dark" class="direction-tag">
              {{ directionLabel(market.direction) }} {{ market.score }}分
            </el-tag>
            <span v-else class="no-data">暂无</span>
          </div>
          <div class="market-reason" v-if="market.reason">{{ market.reason }}</div>
        </div>
      </div>

      <div class="detail-section" v-if="riskEventList.length > 0">
        <div class="section-title">风险事件</div>
        <div class="risk-item" v-for="(item, index) in riskEventList" :key="index">
          <el-icon class="risk-icon"><Warning /></el-icon>
          <span>{{ item }}</span>
        </div>
      </div>

      <div class="detail-section" v-if="detail.errorMsg">
        <div class="section-title error-title">错误信息</div>
        <div class="section-body error-body">{{ detail.errorMsg }}</div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="open = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="SentimentAnalysis">
import { listAnalysis, getAnalysis, runAnalysis } from '@/api/sentiment';

const { proxy } = getCurrentInstance();

const analysisList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const analyzeLoading = ref(false);
const total = ref(0);
const open = ref(false);
const detail = ref({});
const dateRange = ref([]);

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  status: undefined
});

const detailMarkets = computed(() => [
  { name: '美股三大指数', direction: detail.value.usDirection, score: detail.value.usScore, reason: detail.value.usReason },
  { name: '港股指数', direction: detail.value.hkDirection, score: detail.value.hkScore, reason: detail.value.hkReason },
  { name: 'A股指数', direction: detail.value.aDirection, score: detail.value.aScore, reason: detail.value.aReason }
]);

const riskEventList = computed(() => {
  const raw = detail.value.riskEvents;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map(item => (typeof item === 'string' ? item : JSON.stringify(item)));
  } catch (e) {
    /* 非JSON字符串，按分隔符切分 */
  }
  return String(raw).split(/[\n;；]/).map(s => s.trim()).filter(s => s);
});

/** 方向归一化 */
function normalizeDirection(direction) {
  if (!direction) return '';
  const d = String(direction).toLowerCase();
  if (d.includes('多') || d.includes('bull') || d.includes('up') || d.includes('涨') || d.includes('positive')) return 'up';
  if (d.includes('空') || d.includes('bear') || d.includes('down') || d.includes('跌') || d.includes('negative')) return 'down';
  return 'flat';
}

/** 利多红、利空绿（中国习惯）、中性灰 */
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
  return '中性';
}

/** 查询分析列表 */
function getList() {
  loading.value = true;
  listAnalysis(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    analysisList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  dateRange.value = [];
  proxy.resetForm('queryRef');
  handleQuery();
}

/** 行点击 */
function handleRowClick(row) {
  handleDetail(row);
}

/** 查看详情 */
function handleDetail(row) {
  getAnalysis(row.analysisId).then(response => {
    detail.value = response.data || row;
    open.value = true;
  }).catch(() => {
    detail.value = row;
    open.value = true;
  });
}

/** 手动分析 */
function handleAnalyze() {
  analyzeLoading.value = true;
  runAnalysis().then(() => {
    proxy.$modal.msgSuccess('AI分析任务已触发');
    getList();
  }).finally(() => {
    analyzeLoading.value = false;
  });
}

getList();
</script>

<style lang="scss" scoped>
.direction-tag {
  border: none;
  color: #fff;
}
.detail-section {
  margin-top: 18px;
  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-emphasis, #303133);
    margin-bottom: 8px;
    padding-left: 8px;
    border-left: 3px solid #409eff;
    &.error-title {
      border-left-color: #f56c6c;
    }
  }
  .section-body {
    font-size: 13px;
    color: #606266;
    line-height: 1.8;
    white-space: pre-wrap;
    &.error-body {
      color: #f56c6c;
      background: #fef0f0;
      border-radius: 6px;
      padding: 10px 12px;
    }
  }
  .market-block {
    margin-bottom: 12px;
    .market-line {
      display: flex;
      align-items: center;
      gap: 10px;
      .market-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-emphasis, #303133);
      }
      .no-data {
        color: #909399;
        font-size: 13px;
      }
    }
    .market-reason {
      margin-top: 4px;
      font-size: 13px;
      color: #606266;
      line-height: 1.7;
    }
  }
  .risk-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 6px;
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
