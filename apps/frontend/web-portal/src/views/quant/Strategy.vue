<template>
  <PageFrame
    title="策略信号"
    subtitle="策略卡片 · 信号流 · 对齐 /quant/strategy"
    badge="「策略信号 /quant/strategy」"
    :loading="loading"
  >
    <template #actions>
      <el-button type="primary" @click="createOpen = true">新建策略</el-button>
      <el-button :loading="running" @click="run">运行</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · stubStrategies / stubStrategySignals" type="warning" show-icon :closable="false" />

    <div class="chip-row">
      <button type="button" class="filter-chip" :class="{ active: status === '' }" @click="status = ''">全部</button>
      <button type="button" class="filter-chip" :class="{ active: status === 'running' }" @click="status = 'running'">运行中</button>
      <button type="button" class="filter-chip" :class="{ active: status === 'paused' }" @click="status = 'paused'">暂停</button>
    </div>

    <div class="stat-strip">
      <article class="stat-tile glass-panel">
        <span>策略数</span>
        <strong class="numeric">{{ strategies.length }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>运行中</span>
        <strong class="numeric">{{ strategies.filter((s) => s.status === 'running').length }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>今日信号</span>
        <strong class="numeric">{{ signals.length }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>可交易</span>
        <strong class="numeric">{{ actionable }}</strong>
      </article>
    </div>

    <div class="card-grid">
      <article v-for="s in filteredStrategies" :key="s.id || s.name" class="glass-panel strat-card">
        <div class="card-head">
          <strong>{{ s.name }}</strong>
          <el-tag size="small" :type="s.status === 'running' ? 'success' : 'info'">{{ s.status === 'running' ? '运行中' : '暂停' }}</el-tag>
        </div>
        <p class="muted">{{ s.note || s.profile || '--' }}</p>
        <div class="mini-metrics">
          <span>标的 <b class="numeric">{{ s.symbolsCount ?? '--' }}</b></span>
          <span>信号 <b class="numeric">{{ s.signalCount ?? '--' }}</b></span>
          <span>胜率 <b class="numeric">{{ winText(s.winRate) }}</b></span>
        </div>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <template #header><h3>信号流</h3></template>
      <div v-if="signals.length" class="signal-list">
        <article v-for="row in signals" :key="row.id || `${row.symbol}-${row.createdAt}`" class="signal-item">
          <span class="side-tag" :class="sideClass(row.signal)">{{ row.signal || '--' }}</span>
          <div>
            <strong>{{ row.symbol }}</strong>
            <span class="muted"> {{ row.name || '' }}</span>
          </div>
          <span class="numeric muted">强度 {{ strengthText(row) }}</span>
          <time class="numeric muted">{{ row.createdAt || row.time || '' }}</time>
        </article>
      </div>
      <el-empty v-else description="暂无信号" :image-size="56" />
    </el-card>

    <el-dialog v-model="createOpen" title="新建策略" width="420px">
      <el-form label-width="72px">
        <el-form-item label="名称"><el-input v-model="draft.name" placeholder="如 多因子动量" /></el-form-item>
        <el-form-item label="配置"><el-input v-model="draft.profile" placeholder="momentum / reversion" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" @click="createLocal">创建（本地）</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>BUY 红 / SELL 绿 · GET /quant/strategy/history · POST /quant/strategy/run</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { listStrategyHistory, runStrategy } from '@/api/quant'
import { unwrap, unwrapList } from '@/utils/list'
import { stubStrategies, stubStrategySignals } from '@/utils/stubs'

const loading = ref(false)
const running = ref(false)
const usingStub = ref(false)
const status = ref('')
const strategies = ref([])
const signals = ref([])
const createOpen = ref(false)
const draft = reactive({ name: '', profile: 'momentum' })

const filteredStrategies = computed(() => strategies.value.filter((s) => !status.value || s.status === status.value))
const actionable = computed(() => signals.value.filter((s) => ['BUY', 'SELL'].includes(String(s.signal || '').toUpperCase())).length)

function winText(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return `${(n > 1 ? n : n * 100).toFixed(1)}%`
}
function strengthText(row) {
  const n = Number(row.strength ?? row.confidence ?? (Number(row.score) / 100))
  if (!Number.isFinite(n)) return '--'
  return n > 1 ? n.toFixed(0) : n.toFixed(2)
}
function sideClass(signal) {
  const s = String(signal || '').toUpperCase()
  if (s === 'BUY' || s === '买入') return 'is-buy'
  if (s === 'SELL' || s === '卖出') return 'is-sell'
  return 'is-hold'
}

function applyStub() {
  usingStub.value = true
  strategies.value = stubStrategies()
  signals.value = stubStrategySignals()
}

async function load() {
  loading.value = true
  try {
    const res = await listStrategyHistory({ pageNum: 1, pageSize: 50 })
    const data = unwrap(res)
    const list = data.signals || unwrapList(res)
    if (data.strategies?.length) strategies.value = data.strategies
    if (list.length) {
      signals.value = list
      if (!data.strategies?.length) {
        strategies.value = [{
          id: 'live',
          name: data.profile || '默认策略',
          status: 'running',
          profile: data.profile,
          symbolsCount: data.symbolsCount,
          signalCount: data.signalCount || list.length,
          winRate: data.winRate
        }]
      }
      usingStub.value = false
    } else applyStub()
  } catch {
    applyStub()
  } finally {
    loading.value = false
  }
}

async function run() {
  running.value = true
  try {
    await runStrategy({})
    ElMessage.success('已运行')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '运行失败')
  } finally {
    running.value = false
  }
}

function createLocal() {
  if (!draft.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  strategies.value.unshift({
    id: `local-${Date.now()}`,
    name: draft.name.trim(),
    status: 'paused',
    profile: draft.profile,
    symbolsCount: 0,
    signalCount: 0,
    note: '本地草稿，待接入策略配置 API'
  })
  createOpen.value = false
  draft.name = ''
  ElMessage.success('已加入列表（本地）')
}

onMounted(load)
</script>

<style scoped>
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.strat-card { padding: 12px; display: grid; gap: 6px; }
.card-head, .mini-metrics { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.mini-metrics { font-size: 12px; color: var(--text-secondary); }
h3 { margin: 0; font-size: 15px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.signal-list { display: grid; gap: 8px; }
.signal-item {
  display: grid;
  grid-template-columns: 64px 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--control-border);
}
.side-tag {
  display: inline-flex;
  justify-content: center;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.side-tag.is-buy {
  color: var(--order-buy-solid);
  background: color-mix(in srgb, var(--stat-up) var(--chip-fill), transparent);
}
.side-tag.is-sell {
  color: var(--order-sell-solid);
  background: color-mix(in srgb, var(--stat-down) var(--chip-fill), transparent);
}
.side-tag.is-hold {
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
}
@media (max-width: 900px) { .card-grid { grid-template-columns: 1fr; } }
</style>
