<template>
  <PageFrame title="全部股票" :loading="loading">
    <template #actions>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
      </el-radio-group>
      <el-input v-model="keyword" clearable placeholder="代码 / 名称" style="width:180px" @keyup.enter="load" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无标的">
        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">{{ marketLabel(row.market) }}</template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="128" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }">{{ fmtPx(row.price) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate)">{{ fmtChange(row.changeRate) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="tradeDate" label="最新日" width="118" />
        <el-table-column width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(terminalRoute(row))">行情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { listInstrumentUniverse } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { marketLabel, unwrap, unwrapList, unwrapTotal } from '@/utils/list'
import { terminalRoute } from '@/utils/nav'

const loading = ref(false)
const market = ref('')
const keyword = ref('')
const list = ref([])
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await listInstrumentUniverse({
      market: market.value || undefined,
      keyword: keyword.value || undefined,
      pageNum: page.value,
      pageSize: pageSize.value
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

onMounted(load)
</script>

<style scoped>
.pager { display: flex; justify-content: flex-end; padding-top: 10px; }
</style>
