<template>
  <PageFrame
    title="智能选股"
    :subtitle="heroSub"
    badge="「智能选股 /market/recommendations」"
    :loading="loading"
  >
    <template #actions>
      <el-button :loading="moodLoading" @click="refreshMood">刷新情绪</el-button>
      <el-button type="primary" :loading="running" @click="run">生成选股单</el-button>
    </template>

    <div class="toolbar">
      <div class="chip-row">
        <button
          v-for="s in strategies"
          :key="s"
          type="button"
          class="filter-chip"
          :class="{ active: strategy === s }"
          @click="strategy = s"
        >{{ s }}</button>
      </div>
      <el-radio-group v-model="market" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="US">美股</el-radio-button>
        <el-radio-button value="HK">港股</el-radio-button>
        <el-radio-button value="CN">A股</el-radio-button>
      </el-radio-group>
    </div>

    <el-empty v-if="!loading && !visible.length" :description="emptyText" />
    <div v-else class="rec-grid">
      <article v-for="row in visible" :key="row.symbol + row.market" class="rec-card glass-panel" @click="goTerminal($router, row)">
        <div class="rec-top">
          <div class="score numeric">{{ row.pickScore ?? row.score ?? '--' }}</div>
          <div class="rec-id">
            <strong>{{ row.symbol }}</strong>
            <span>{{ row.name }}</span>
            <em class="mkt-tag" :class="`is-${String(row.market || '').toLowerCase()}`">{{ marketLabel(row.market) }}</em>
          </div>
          <b :class="changeClass(row.changePct ?? row.changeRate)">{{ fmtChange(row.changePct ?? row.changeRate) }}</b>
        </div>
        <p>{{ row.summary || row.reason || '规则初筛入选，等待 AI 研判补全文案。' }}</p>
        <div class="rec-foot">
          <span class="filter-chip">{{ strategyOf(row) }}</span>
          <span class="rec-pill" :class="recoClass(row.recommendation)">{{ row.recommendation || '观望' }}</span>
        </div>
      </article>
    </div>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { getStockPickLatest, getStockPickMood, refreshStockPickMood, runStockPick } from '@/api/market'
import { changeClass, fmtChange } from '@/utils/format'
import { goTerminal, marketLabel, unwrap, unwrapList } from '@/utils/list'

const FALLBACK = ['全部策略', '动量突破', '机构净流入', '估值修复', '事件驱动', '相对强度']
const loading = ref(false)
const running = ref(false)
const moodLoading = ref(false)
const market = ref('')
const strategy = ref('全部策略')
const items = ref([])
const tradeDate = ref('')
const modelName = ref('Grok 4.6')

const heroSub = computed(() =>
  `规则初筛 + AI 研判 (指标 / 舆情 / 开盘指数) · 默认 ${modelName.value} · 交易日 ${tradeDate.value || '--'}`
)
const emptyText = computed(() => '暂无选股单，点击「生成选股单」或等待收盘任务')
const strategies = computed(() => {
  const found = [...new Set(items.value.map(strategyOf).filter(Boolean))]
  return found.length ? ['全部策略', ...found] : FALLBACK
})
const visible = computed(() => {
  if (strategy.value === '全部策略') return items.value
  return items.value.filter((r) => strategyOf(r) === strategy.value)
})

function strategyOf(row) {
  return row.strategy || row.tag || row.theme || row.pickTag || '规则初筛'
}
function recoClass(v) {
  if (v === '买入' || v === '加仓' || v === '关注') return 'buy'
  if (v === '观望偏多') return 'lean'
  if (v === '回避' || v === '减仓') return 'sell'
  return 'wait'
}

async function load() {
  loading.value = true
  try {
    const [latestRes, moodRes] = await Promise.allSettled([
      getStockPickLatest({ market: market.value || undefined }),
      getStockPickMood()
    ])
    if (latestRes.status === 'fulfilled') {
      const data = unwrap(latestRes.value)
      items.value = data.items || unwrapList(latestRes.value)
      tradeDate.value = data.tradeDate || tradeDate.value
      modelName.value = data.modelName || modelName.value
    }
    if (moodRes.status === 'fulfilled') {
      const mood = unwrap(moodRes.value)
      modelName.value = mood.modelName || modelName.value
    }
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function refreshMood() {
  moodLoading.value = true
  try {
    await refreshStockPickMood()
    ElMessage.success('情绪已刷新')
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '刷新失败')
  } finally {
    moodLoading.value = false
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

<style scoped>
.toolbar { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.rec-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.rec-card { padding: 12px; display: grid; gap: 8px; cursor: pointer; }
.rec-top { display: grid; grid-template-columns: 40px 1fr auto; gap: 8px; align-items: start; }
.score {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface-soft) 80%, transparent);
  font-weight: 800;
}
.rec-id { display: grid; gap: 2px; }
.rec-id strong { color: var(--text-emphasis); }
.rec-id span { font-size: 12px; color: var(--text-secondary); }
.rec-card p { margin: 0; font-size: 13px; color: var(--text-primary); min-height: 38px; }
.rec-foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.rec-pill {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid var(--control-border);
}
.rec-pill.buy { color: var(--stat-up); border-color: color-mix(in srgb, var(--stat-up) 40%, transparent); }
.rec-pill.lean { color: #d97706; border-color: color-mix(in srgb, #d97706 40%, transparent); }
.rec-pill.sell { color: var(--stat-down); border-color: color-mix(in srgb, var(--stat-down) 40%, transparent); }
@media (max-width: 1200px) { .rec-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 720px) { .rec-grid { grid-template-columns: 1fr; } }
</style>
