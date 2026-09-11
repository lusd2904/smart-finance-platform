<template>
  <PageFrame title="资讯列表" badge="「资讯列表 /sentiment/news」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="collecting" @click="collect">手动采集</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-card shadow="never" class="glass-panel filter-card">
      <el-form :inline="true" class="compact-form" @submit.prevent="search">
        <el-form-item label="来源">
          <el-select v-model="query.source" clearable placeholder="资讯来源" style="width: 140px">
            <el-option label="东方财富" value="eastmoney" />
            <el-option label="新浪财经" value="sina" />
            <el-option label="同花顺" value="ths" />
            <el-option label="华尔街见闻" value="wallstreetcn" />
            <el-option label="谷歌新闻" value="google_news" />
            <el-option label="金十数据" value="jin10" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="query.title" clearable placeholder="请输入标题" style="width: 180px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="是否已分析">
          <el-select v-model="query.analyzed" clearable placeholder="是否已分析" style="width: 120px">
            <el-option label="已分析" value="1" />
            <el-option label="未分析" value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布时间">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="-"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" size="small" stripe empty-text="暂无资讯">
        <el-table-column prop="newsId" label="编号" width="72" />
        <el-table-column label="来源" width="110">
          <template #default="{ row }">
            <el-tag effect="plain" size="small">{{ sourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button link type="primary" @click="openContent(row)">{{ row.title }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="正文摘要" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="preview">{{ contentPreview(row.content || row.title) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            <span class="numeric">{{ formatTime(row.pubTime || row.createTime) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="是否已分析" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="isAnalyzed(row) ? 'success' : 'info'">
              {{ isAnalyzed(row) ? '已分析' : '未分析' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="72" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openContent(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawer" :title="current.title || '资讯详情'" size="480px" direction="rtl" destroy-on-close>
      <div class="news-drawer">
        <div class="meta-row">
          <el-tag effect="plain" size="small">{{ sourceLabel(current.source) }}</el-tag>
          <el-tag size="small" :type="isAnalyzed(current) ? 'success' : 'info'">
            {{ isAnalyzed(current) ? '已分析' : '未分析' }}
          </el-tag>
          <span class="meta-time numeric">{{ formatTime(current.pubTime || current.createTime) || '--' }}</span>
        </div>
        <h3>{{ current.title }}</h3>
        <div v-if="paragraphs.length" class="drawer-body">
          <p v-for="(para, idx) in paragraphs" :key="idx">{{ para }}</p>
        </div>
        <el-empty v-else description="暂无正文内容" :image-size="48" />
        <div v-if="current.newsId" class="drawer-footer">编号 #{{ current.newsId }}</div>
      </div>
    </el-drawer>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { collectNews, listNews } from '@/api/sentiment'
import { unwrap, unwrapList, unwrapTotal } from '@/utils/list'

const loading = ref(false)
const collecting = ref(false)
const list = ref([])
const page = ref(1)
const total = ref(0)
const dateRange = ref([])
const drawer = ref(false)
const current = ref({})
const query = ref({ source: undefined, title: '', analyzed: undefined })

const paragraphs = computed(() => {
  const text = String(current.value.content || current.value.title || '').trim()
  return text
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean)
})

function formatTime(v) {
  const s = String(v || '').replace('T', ' ').trim()
  return s ? s.slice(0, 19) : ''
}

function isAnalyzed(row) {
  return String(row?.analyzed) === '1'
}

function sourceLabel(source) {
  const map = {
    eastmoney: '东方财富',
    sina: '新浪财经',
    ths: '同花顺',
    cls: '财联社/同花顺',
    wallstreetcn: '华尔街见闻',
    google_news: '谷歌新闻',
    jin10: '金十数据'
  }
  return map[source] || source || '--'
}

function contentPreview(text) {
  const s = String(text || '').replace(/\s+/g, ' ').trim()
  if (!s) return '--'
  return s.length > 80 ? `${s.slice(0, 80)}…` : s
}

function dateParams() {
  const [begin, end] = dateRange.value || []
  if (!begin || !end) return {}
  return { beginTime: String(begin).slice(0, 10), endTime: String(end).slice(0, 10) }
}

async function load() {
  loading.value = true
  try {
    const res = await listNews({
      pageNum: page.value,
      pageSize: 20,
      source: query.value.source || undefined,
      title: query.value.title?.trim() || undefined,
      analyzed: query.value.analyzed || undefined,
      ...dateParams()
    })
    list.value = unwrapList(res)
    total.value = unwrapTotal(res, list.value.length)
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  query.value = { source: undefined, title: '', analyzed: undefined }
  dateRange.value = []
  search()
}

function openContent(row) {
  current.value = { ...row }
  drawer.value = true
}

async function collect() {
  collecting.value = true
  try {
    const res = await collectNews()
    const d = unwrap(res)
    ElMessage.success(res?.msg || (d.accepted ? '已加入后台队列' : '采集任务已触发'))
    if (!d.accepted) load()
  } catch (e) {
    ElMessage.error(e?.message || '采集失败')
  } finally {
    collecting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.filter-card {
  padding: 8px 10px !important;
}
.compact-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 4px;
}
.compact-form :deep(.el-form-item) {
  margin-bottom: 0 !important;
  margin-right: 8px;
}
.preview {
  color: var(--text-secondary);
  font-size: 13px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}
.news-drawer .meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.meta-time {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: 13px;
}
.news-drawer h3 {
  margin: 0 0 12px;
  font-size: 16px;
  line-height: 1.45;
  color: var(--text-emphasis);
}
.drawer-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-emphasis);
}
.drawer-body p {
  margin: 0 0 10px;
}
.drawer-footer {
  margin-top: 16px;
  padding-top: 10px;
  border-top: 1px solid var(--border-soft);
  color: var(--text-secondary);
  font-size: 12px;
}
:deep(.el-empty) {
  padding: 8px 0;
}
:deep(.el-table) {
  font-size: 13px;
}
:deep(.el-table th.el-table__cell),
:deep(.el-table td.el-table__cell) {
  padding: 4px 0;
}
</style>
