<template>
  <PageFrame title="智能选股" :loading="loading">
    <template #actions>
      <el-select v-model="tradeDate" clearable placeholder="交易日" style="width:132px" @change="load">
        <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
      </el-select>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="running" @click="run">生成选股单</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="stat-strip" v-if="moodCards.length">
      <article v-for="c in moodCards" :key="c.market" class="stat-tile glass-panel">
        <span>{{ c.label }}</span>
        <strong>{{ c.sentText }}</strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="items" stripe empty-text="暂无选股">
        <el-table-column prop="rankNo" label="#" width="52" />
        <el-table-column prop="market" label="市场" width="76">
          <template #default="{ row }">{{ marketLabel(row.market) }}</template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="110" />
        <el-table-column label="最新价" width="100" align="right">
          <template #default="{ row }">{{ fmtPx(row.price) }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate)">{{ fmtChange(row.changeRate) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="得分" width="80" align="right" />
        <el-table-column prop="recommendation" label="建议" width="90" />
      </el-table>
    </el-card>
  </PageFrame>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { getStockPickDates, getStockPickLatest, getStockPickMood, runStockPick } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { marketLabel, unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const running = ref(false)
const market = ref('')
const tradeDate = ref('')
const dates = ref([])
const items = ref([])
const moodCards = ref([])

async function load() {
  loading.value = true
  try {
    const [latestRes, moodRes, dateRes] = await Promise.allSettled([
      getStockPickLatest({ market: market.value || undefined, tradeDate: tradeDate.value || undefined }),
      getStockPickMood(),
      getStockPickDates()
    ])
    if (latestRes.status === 'fulfilled') {
      const data = unwrap(latestRes.value)
      items.value = data.items || unwrapList(latestRes.value)
      if (!tradeDate.value && data.tradeDate) tradeDate.value = data.tradeDate
    }
    if (moodRes.status === 'fulfilled') {
      const mood = unwrap(moodRes.value)
      const markets = mood.markets || mood.items || []
      moodCards.value = markets.map((m) => ({
        market: m.market,
        label: marketLabel(m.market),
        sentText: m.sentimentText || m.sentText || m.score || '--'
      }))
    }
    if (dateRes.status === 'fulfilled') {
      dates.value = unwrapList(dateRes.value).map((d) => (typeof d === 'string' ? d : d.tradeDate)).filter(Boolean)
    }
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function run() {
  running.value = true
  try {
    await runStockPick()
    ElMessage.success('已生成')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '生成失败')
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>
