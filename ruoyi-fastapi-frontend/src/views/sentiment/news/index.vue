<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="来源" prop="source">
        <el-select v-model="queryParams.source" placeholder="资讯来源" clearable style="width: 160px">
          <el-option label="东方财富" value="eastmoney" />
          <el-option label="新浪财经" value="sina" />
          <el-option label="同花顺" value="ths" />
          <el-option label="华尔街见闻" value="wallstreetcn" />
          <el-option label="谷歌新闻" value="google_news" />
          <el-option label="金十数据" value="jin10" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题" prop="title">
        <el-input
          v-model="queryParams.title"
          placeholder="请输入标题"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="是否已分析" prop="analyzed">
        <el-select v-model="queryParams.analyzed" placeholder="是否已分析" clearable style="width: 140px">
          <el-option label="已分析" value="1" />
          <el-option label="未分析" value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="发布时间" style="width: 308px">
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
          type="primary"
          plain
          icon="Download"
          :loading="collectLoading"
          @click="handleCollect"
          v-hasPermi="['sentiment:news:collect']"
        >手动采集</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['sentiment:news:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="newsList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="编号" align="center" prop="newsId" width="80" />
      <el-table-column label="来源" align="center" prop="source" width="110">
        <template #default="scope">
          <el-tag effect="plain">{{ sourceLabel(scope.row.source) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标题" align="left" prop="title" :show-overflow-tooltip="true" min-width="280">
        <template #default="scope">
          <el-link type="primary" :underline="false" @click="openContent(scope.row)">
            {{ scope.row.title }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="正文摘要" align="left" prop="content" :show-overflow-tooltip="true" min-width="220">
        <template #default="scope">
          <span class="content-preview">{{ contentPreview(scope.row.content || scope.row.title) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="发布时间" align="center" prop="pubTime" width="170">
        <template #default="scope">
          <span>{{ parseTime(scope.row.pubTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="是否已分析" align="center" prop="analyzed" width="110">
        <template #default="scope">
          <el-tag :type="String(scope.row.analyzed) === '1' ? 'success' : 'info'">
            {{ String(scope.row.analyzed) === '1' ? '已分析' : '未分析' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="采集时间" align="center" prop="createTime" width="170">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="140" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openContent(scope.row)">查看</el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['sentiment:news:remove']">删除</el-button>
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

    <!-- 站内内容查看：不跳转原页面 -->
    <el-drawer
      v-model="drawerVisible"
      :title="currentNews.title || '资讯详情'"
      size="520px"
      direction="rtl"
      destroy-on-close
    >
      <div class="news-drawer" v-if="currentNews">
        <div class="meta-row">
          <el-tag effect="plain" size="small">{{ sourceLabel(currentNews.source) }}</el-tag>
          <el-tag
            size="small"
            :type="String(currentNews.analyzed) === '1' ? 'success' : 'info'"
            style="margin-left: 8px"
          >
            {{ String(currentNews.analyzed) === '1' ? '已分析' : '未分析' }}
          </el-tag>
          <span class="meta-time">{{ parseTime(currentNews.pubTime) || parseTime(currentNews.createTime) || '--' }}</span>
        </div>
        <h3 class="drawer-title">{{ currentNews.title }}</h3>
        <div class="drawer-body">
          <template v-if="displayContent">
            <p v-for="(para, idx) in contentParagraphs" :key="idx" class="para">{{ para }}</p>
          </template>
          <el-empty v-else description="暂无正文内容" :image-size="80" />
        </div>
        <div class="drawer-footer" v-if="currentNews.newsId">
          <span class="footer-id">编号 #{{ currentNews.newsId }}</span>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup name="SentimentNews">
import { listNews, delNews, collectNews } from '@/api/sentiment';

const { proxy } = getCurrentInstance();

const newsList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const collectLoading = ref(false);
const ids = ref([]);
const multiple = ref(true);
const total = ref(0);
const dateRange = ref([]);
const drawerVisible = ref(false);
const currentNews = ref({});

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  source: undefined,
  title: undefined,
  analyzed: undefined
});

const displayContent = computed(() => {
  const c = (currentNews.value.content || '').trim();
  const t = (currentNews.value.title || '').trim();
  return c || t;
});

const contentParagraphs = computed(() => {
  const text = displayContent.value || '';
  return text
    .split(/\n+/)
    .map(s => s.trim())
    .filter(Boolean);
});

function sourceLabel(source) {
  const map = {
    eastmoney: '东方财富',
    sina: '新浪财经',
    ths: '同花顺',
    cls: '财联社/同花顺',
    wallstreetcn: '华尔街见闻',
    google_news: '谷歌新闻',
    jin10: '金十数据'
  };
  return map[source] || source || '--';
}

function contentPreview(text) {
  const s = (text || '').replace(/\s+/g, ' ').trim();
  if (!s) return '--';
  return s.length > 80 ? s.slice(0, 80) + '…' : s;
}

/** 查询资讯列表 */
function getList() {
  loading.value = true;
  listNews(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    newsList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  }).catch(() => {
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

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.newsId);
  multiple.value = !selection.length;
}

/** 站内打开正文（绝不跳转原页面） */
function openContent(row) {
  currentNews.value = { ...row };
  drawerVisible.value = true;
}

/** 手动采集 */
function handleCollect() {
  collectLoading.value = true;
  collectNews().then((res) => {
    const d = (res && res.data) || {};
    proxy.$modal.msgSuccess((res && res.msg) || (d.accepted ? '已加入后台队列' : '采集任务已触发'));
    if (!d.accepted) getList();
  }).finally(() => {
    collectLoading.value = false;
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const newsIds = row.newsId || ids.value;
  proxy.$modal.confirm('是否确认删除资讯编号为"' + newsIds + '"的数据项？').then(function() {
    return delNews(newsIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess('删除成功');
  }).catch(() => {});
}

getList();
</script>

<style scoped>
.content-preview {
  color: #606266;
  font-size: 13px;
}
.news-drawer .meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}
.news-drawer .meta-time {
  margin-left: auto;
  color: #909399;
  font-size: 13px;
}
.news-drawer .drawer-title {
  margin: 0 0 16px;
  font-size: 18px;
  line-height: 1.5;
  color: var(--text-emphasis, #303133);
  word-break: break-word;
}
.news-drawer .drawer-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-emphasis, #303133);
  white-space: pre-wrap;
  word-break: break-word;
}
.news-drawer .para {
  margin: 0 0 12px;
}
.news-drawer .drawer-footer {
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
  color: #909399;
  font-size: 12px;
}
</style>
