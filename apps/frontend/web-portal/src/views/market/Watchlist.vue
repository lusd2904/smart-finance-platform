<template>
  <PageFrame title="自选清单" :loading="loading">
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:160px" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>自选</span><strong>{{ items.length }}</strong></article>
      <article class="stat-tile glass-panel"><span>上涨</span><strong class="up">{{ upCount }}</strong></article>
      <article class="stat-tile glass-panel"><span>下跌</span><strong class="down">{{ downCount }}</strong></article>
      <article class="stat-tile glass-panel"><span>分析</span><strong>{{ analysisCount }}</strong></article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无自选">
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="130" />
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }">{{ fmtPx(row.price) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate)">{{ fmtChange(row.changeRate) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="recommendation" label="建议" width="90" />
        <el-table-column width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push('/trade/terminal')">行情</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { delMarketWatchlist, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const keyword = ref('')
const items = ref([])
const analysisCount = ref(0)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw))
})
const upCount = computed(() => items.value.filter((r) => Number(r.changeRate) > 0).length)
const downCount = computed(() => items.value.filter((r) => Number(r.changeRate) < 0).length)

async function load() {
  loading.value = true
  try {
    const [listRes, ovRes] = await Promise.allSettled([listMarketWatchlist(), getMarketWatchlistOverview()])
    if (listRes.status === 'fulfilled') items.value = unwrapList(listRes.value)
    if (ovRes.status === 'fulfilled') {
      const ov = unwrap(ovRes.value)
      if (!items.value.length) items.value = ov.items || ov.watchlist || []
      analysisCount.value = ov.analyzedCount ?? ov.analysisCount ?? (ov.items || []).filter((x) => x.recommendation).length
    }
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function remove(row) {
  try {
    await delMarketWatchlist(row.id || row.watchlistId || row.symbol)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(load)
</script>
