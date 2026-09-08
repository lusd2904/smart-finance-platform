<template>
  <PageFrame title="市场分析" :loading="loading">
    <template #actions>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="analyzing" @click="analyze">立即分析</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article v-for="item in latest" :key="item.market" class="stat-tile glass-panel review-latest">
        <span>{{ item.marketLabel || item.market }}</span>
        <strong>
          <el-tag size="small" :type="item.stance === '偏多' ? 'danger' : item.stance === '偏空' ? 'success' : 'info'">
            {{ item.stance || '待分析' }}
          </el-tag>
        </strong>
        <span>{{ item.tradeDate || '--' }} · {{ item.score ?? '--' }}</span>
        <p>{{ item.summary || '暂无报告' }}</p>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>历史记录</h3></template>
      <el-table :data="history" stripe empty-text="暂无记录">
        <el-table-column prop="tradeDate" label="交易日" width="120" />
        <el-table-column label="市场" width="80">
          <template #default="{ row }">{{ row.marketLabel || row.market }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="stance" label="立场" width="80" />
        <el-table-column prop="score" label="温度" width="80" align="right" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { analyzeMarketReview, getMarketReviewHistory, getMarketReviewLatest } from '@/api/market'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const analyzing = ref(false)
const market = ref('')
const latest = ref([])
const history = ref([])

async function load() {
  loading.value = true
  try {
    const [latestRes, histRes] = await Promise.allSettled([
      getMarketReviewLatest(),
      getMarketReviewHistory({ market: market.value || undefined })
    ])
    if (latestRes.status === 'fulfilled') {
      const data = unwrap(latestRes.value)
      latest.value = data.items || unwrapList(latestRes.value)
    }
    if (histRes.status === 'fulfilled') {
      history.value = unwrap(histRes.value).items || unwrapList(histRes.value)
    }
  } catch {
    latest.value = []
    history.value = []
  } finally {
    loading.value = false
  }
}

async function analyze() {
  analyzing.value = true
  try {
    await analyzeMarketReview(market.value || undefined)
    ElMessage.success('已提交')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
h3 { margin: 0; font-size: 15px; }
.review-latest p { margin: 0; color: var(--text-secondary); font-size: 13px; }
</style>
