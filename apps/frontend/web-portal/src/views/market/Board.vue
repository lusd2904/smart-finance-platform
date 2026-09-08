<template>
  <PageFrame title="行情台" :loading="loading">
    <template #actions>
      <el-select v-model="market" clearable placeholder="市场" style="width:110px" @change="load">
        <el-option label="全部" value="" />
        <el-option label="美股" value="US" />
        <el-option label="港股" value="HK" />
        <el-option label="A股" value="CN" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="代码/名称" style="width:160px" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip" v-if="indices.length">
      <article v-for="ix in indices" :key="ix.symbol" class="stat-tile glass-panel">
        <span>{{ ix.name }} {{ ix.symbol }}</span>
        <strong :class="changeClass(ix.changeRate ?? ix.change)">{{ fmtPx(ix.price) }}</strong>
        <span :class="changeClass(ix.changeRate ?? ix.change)">{{ fmtChange(ix.changeRate ?? ix.change) }}</span>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无报价">
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }">{{ fmtPx(row.price) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="120" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate ?? row.change)">{{ fmtChange(row.changeRate ?? row.change) }}</span>
          </template>
        </el-table-column>
        <el-table-column width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(terminalRoute(row))">行情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getBoardQuotes, getMarketIndexQuotes } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'

const loading = ref(false)
const market = ref('')
const keyword = ref('')
const rows = ref([])
const indices = ref([])

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  let arr = rows.value
  if (kw) arr = arr.filter((r) => `${r.symbol} ${r.name}`.toLowerCase().includes(kw))
  return arr
})

async function load() {
  loading.value = true
  try {
    const [boardRes, idxRes] = await Promise.allSettled([
      getBoardQuotes({ market: market.value || undefined }),
      getMarketIndexQuotes()
    ])
    if (boardRes.status === 'fulfilled') {
      const data = unwrap(boardRes.value)
      rows.value = (data.quotes || data.items || unwrapList(boardRes.value)).filter((r) => {
        const cat = String(r.category || r.kind || '').toLowerCase()
        return !cat.includes('index')
      })
    }
    if (idxRes.status === 'fulfilled') {
      indices.value = unwrapList(idxRes.value).slice(0, 4)
    }
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
