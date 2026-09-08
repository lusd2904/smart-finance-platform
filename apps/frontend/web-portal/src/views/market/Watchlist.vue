<template>
  <PageFrame
    title="自选清单"
    subtitle="按登录账号隔离 · 分组筛选 · 涨跌一目了然 · 迷你走势 stub"
    badge="「自选清单 /market/watchlist」"
    :loading="loading"
  >
    <template #actions>
      <div class="hero-stats">
        <div><span>自选数</span><strong class="numeric">{{ items.length }}</strong></div>
        <div><span>上涨</span><strong class="numeric up">{{ upCount }}</strong></div>
        <div><span>下跌</span><strong class="numeric down">{{ downCount }}</strong></div>
      </div>
    </template>

    <div class="toolbar">
      <div class="chip-row">
        <button type="button" class="filter-chip" :class="{ active: group === '' }" @click="group = ''">全部 {{ items.length }}</button>
        <button
          v-for="g in groups"
          :key="g.name"
          type="button"
          class="filter-chip"
          :class="{ active: group === g.name }"
          @click="group = g.name"
        >{{ g.name }} {{ g.count }}</button>
      </div>
      <div class="toolbar-acts">
        <el-input v-model="keyword" clearable placeholder="搜索代码 / 名称" style="width:180px" :prefix-icon="Search" />
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="open = true">+ 新增自选</el-button>
      </div>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无自选" @row-click="openRow">
        <el-table-column prop="symbol" label="代码" width="110" />
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column label="市场" width="88">
          <template #default="{ row }">
            <span class="mkt-tag" :class="`is-${String(row.market || '').toLowerCase()}`">{{ marketLabel(row.market) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最新价" width="110" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtPx(row.price ?? row.last) }}</span></template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="110" align="right" sortable>
          <template #default="{ row }">
            <span :class="changeClass(row.changeRate ?? row.changePct)">{{ fmtChange(row.changeRate ?? row.changePct) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="走势" width="90">
          <template #default="{ row }">
            <svg class="spark" viewBox="0 0 60 20" aria-hidden="true">
              <path :d="sparkPath(row)" fill="none" :stroke="sparkColor(row)" stroke-width="1.4" />
            </svg>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawer" :title="current ? `${current.name || ''} ${current.symbol}` : '自选详情'" size="420px">
      <template v-if="current">
        <div class="drawer-quote">
          <strong class="numeric">{{ fmtPx(current.price ?? current.last) }}</strong>
          <span :class="changeClass(current.changeRate ?? current.changePct)">{{ fmtChange(current.changeRate ?? current.changePct) }}</span>
        </div>
        <p class="muted">{{ marketLabel(current.market) }} · {{ (current.groups || []).join('、') || '未分组' }}</p>
        <p>{{ current.summary || current.note || '暂无分析摘要' }}</p>
        <div class="drawer-acts">
          <el-button type="primary" @click="goTerminal($router, current)">行情</el-button>
          <el-button type="danger" plain @click="remove(current)">删除</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="open" title="新增自选" width="420px">
      <el-form label-width="72px">
        <el-form-item label="市场">
          <el-select v-model="form.market" style="width:100%">
            <el-option label="美股 US" value="US" />
            <el-option label="港股 HK" value="HK" />
            <el-option label="A股 CN" value="CN" />
          </el-select>
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model="form.symbol" placeholder="AAPL / 00700 / 600519" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="form.group" placeholder="可选，如 核心持仓" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="add">确定</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>涨红跌绿 · tabular-nums · glass-panel blur · 迷你走势 STUB</span>
      <span>显示 {{ filtered.length }} / {{ items.length }} · 行点击打开抽屉</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { addMarketWatchlist, delMarketWatchlist, getMarketWatchlistOverview, listMarketWatchlist } from '@/api/market'
import { changeClass, fmtChange, fmtPx, renderSparklinePath } from '@/utils/format'
import { goTerminal, marketLabel, unwrap, unwrapList } from '@/utils/list'

const loading = ref(false)
const saving = ref(false)
const keyword = ref('')
const group = ref('')
const items = ref([])
const drawer = ref(false)
const current = ref(null)
const open = ref(false)
const form = reactive({ market: 'US', symbol: '', group: '' })

const groups = computed(() => {
  const map = {}
  for (const item of items.value) {
    const names = item.groups || item.groupNames || (item.group ? [item.group] : [])
    for (const name of names) {
      if (!name || name === '全部') continue
      map[name] = (map[name] || 0) + 1
    }
  }
  return Object.entries(map).map(([name, count]) => ({ name, count }))
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return items.value.filter((r) => {
    const names = r.groups || r.groupNames || (r.group ? [r.group] : [])
    const groupOk = !group.value || names.includes(group.value)
    const textOk = !kw || `${r.symbol} ${r.name}`.toLowerCase().includes(kw)
    return groupOk && textOk
  })
})
const upCount = computed(() => items.value.filter((r) => Number(r.changeRate ?? r.changePct) > 0).length)
const downCount = computed(() => items.value.filter((r) => Number(r.changeRate ?? r.changePct) < 0).length)

function sparkPath(row) {
  return renderSparklinePath(row.sparkline || row.closes || [100, 101, 99, 102, 103, 101, 104])
}
function sparkColor(row) {
  const n = Number(row.changeRate ?? row.changePct)
  if (!Number.isFinite(n) || n === 0) return 'var(--text-secondary)'
  return n > 0 ? 'var(--stat-up)' : 'var(--stat-down)'
}
function openRow(row) {
  current.value = row
  drawer.value = true
}

async function load() {
  loading.value = true
  try {
    const [listRes, ovRes] = await Promise.allSettled([listMarketWatchlist(), getMarketWatchlistOverview()])
    if (listRes.status === 'fulfilled') items.value = unwrapList(listRes.value)
    if (ovRes.status === 'fulfilled') {
      const ov = unwrap(ovRes.value)
      if (!items.value.length) items.value = ov.items || ov.watchlist || []
    }
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

async function add() {
  if (!form.symbol.trim()) {
    ElMessage.warning('请输入代码')
    return
  }
  saving.value = true
  try {
    await addMarketWatchlist({
      symbol: form.symbol.trim(),
      market: form.market,
      groups: form.group ? [form.group] : undefined,
      note: form.group || '自选'
    })
    ElMessage.success('已加入自选')
    open.value = false
    form.symbol = ''
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '添加失败')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await delMarketWatchlist(row.id || row.watchlistId || row.symbol)
    ElMessage.success('已删除')
    drawer.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.hero-stats { display: flex; gap: 18px; }
.hero-stats div { display: grid; gap: 2px; text-align: right; }
.hero-stats span { font-size: 12px; color: var(--text-secondary); }
.hero-stats strong { font-size: 20px; }
.toolbar, .toolbar-acts, .chip-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.toolbar { justify-content: space-between; }
.spark { width: 60px; height: 20px; display: block; }
.drawer-quote { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.drawer-quote strong { font-size: 28px; }
.drawer-acts { display: flex; gap: 8px; margin-top: 16px; }
.muted { color: var(--text-secondary); font-size: 12px; }
</style>
