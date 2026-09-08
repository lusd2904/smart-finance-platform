<template>
  <PageFrame title="自选清单" :loading="loading">
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:160px" />
      <el-button @click="open = true">新增自选</el-button>
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
            <el-button link type="primary" @click="$router.push(terminalRoute(row))">行情</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog title="新增自选" v-model="open" width="440px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="市场">
          <el-select v-model="form.market" style="width: 100%">
            <el-option label="美股 US" value="US" />
            <el-option label="港股 HK" value="HK" />
            <el-option label="A股 CN" value="CN" />
          </el-select>
        </el-form-item>
        <el-form-item label="代码"><el-input v-model="form.symbol" placeholder="AAPL / 00700 / 600519" /></el-form-item>
        <el-form-item label="分组"><el-input v-model="form.groups" placeholder="核心,持仓" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { addMarketWatchlist, delMarketWatchlist, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'

const loading = ref(false)
const keyword = ref('')
const items = ref([])
const analysisCount = ref(0)
const open = ref(false)
const submitLoading = ref(false)
const form = ref({ symbol: '', market: 'US', groups: '' })

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

async function submitForm() {
  if (!form.value.symbol) {
    ElMessage.warning('请输入代码')
    return
  }
  submitLoading.value = true
  try {
    await addMarketWatchlist({ symbol: form.value.symbol.trim(), market: form.value.market, groups: form.value.groups })
    ElMessage.success('已加入自选')
    open.value = false
    form.value = { symbol: '', market: 'US', groups: '' }
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '添加失败')
  } finally {
    submitLoading.value = false
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
