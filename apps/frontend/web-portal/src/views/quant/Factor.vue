<template>
  <PageFrame
    title="因子分析"
    subtitle="因子库 · IC / IR / 覆盖率 · 对齐 /quant/factor"
    :loading="loading"
  >
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · stubFactors" type="warning" show-icon :closable="false" />

    <div class="chip-row">
      <button type="button" class="filter-chip" :class="{ active: category === '' }" @click="category = ''">全部</button>
      <button
        v-for="c in categories"
        :key="c"
        type="button"
        class="filter-chip"
        :class="{ active: category === c }"
        @click="category = c"
      >{{ c }}</button>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe empty-text="暂无因子" @row-click="openDetail">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="分类" width="100">
          <template #default="{ row }">{{ row.category || row.family || row.familyName || '--' }}</template>
        </el-table-column>
        <el-table-column label="IC" width="100" align="right">
          <template #default="{ row }">
            <span class="numeric" :class="changeClass(icOf(row))">{{ fmtIc(icOf(row)) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="IR" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ fmtIc(irOf(row)) }}</span></template>
        </el-table-column>
        <el-table-column label="覆盖率" width="100" align="right">
          <template #default="{ row }"><span class="numeric">{{ coverageText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="88">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawer" :title="current ? current.name : '因子详情'" size="420px">
      <template v-if="current">
        <p class="muted">{{ current.category || current.family }} · IC {{ fmtIc(icOf(current)) }} · IR {{ fmtIc(irOf(current)) }}</p>
        <p>{{ current.desc || current.description || '收益曲线为 STUB 示意，不代表实盘。' }}</p>
        <h4>收益 stub</h4>
        <ol class="ret-list">
          <li v-for="(v, i) in returnsOf(current)" :key="i">
            T-{{ returnsOf(current).length - i }}
            <span class="numeric" :class="changeClass(v)">{{ v > 0 ? '+' : '' }}{{ Number(v).toFixed(2) }}%</span>
          </li>
        </ol>
      </template>
    </el-drawer>

    <template #legend>
      <span>IC 正红负绿 · tabular-nums · GET /quant/factor/schema + /snapshots · STUB OK</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import PageFrame from '@/components/page/PageFrame.vue'
import { getFactorSchema, listFactorSnapshots } from '@/api/quant'
import { changeClass } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'
import { stubFactors } from '@/utils/stubs'

const loading = ref(false)
const usingStub = ref(false)
const rows = ref([])
const category = ref('')
const drawer = ref(false)
const current = ref(null)

function icOf(row) {
  return Number(row.ic ?? row.icMean ?? row.ic_mean ?? row.score)
}
function irOf(row) {
  return Number(row.ir ?? row.IR ?? row.icIr)
}
function coverageText(row) {
  const n = Number(row.coverage ?? row.coverageRate ?? row.icPositiveRatio)
  if (!Number.isFinite(n)) return '--'
  return `${(n > 1 ? n : n * 100).toFixed(1)}%`
}
function fmtIc(n) {
  if (!Number.isFinite(n)) return '--'
  return n.toFixed(3)
}
function returnsOf(row) {
  return row.returns || row.quantiles || [0.4, -0.2, 0.6, 0.1, -0.3]
}
function normalize(list) {
  return list.map((item) => ({
    name: item.name || item.factorLabel || item.label || item.code || '--',
    category: item.category || item.family || item.familyName || item.group || '其他',
    ic: icOf(item),
    ir: irOf(item),
    coverage: item.coverage ?? item.coverageRate ?? item.icPositiveRatio,
    desc: item.desc || item.description,
    returns: item.returns,
    ...item
  }))
}

const categories = computed(() => [...new Set(rows.value.map((r) => r.category).filter(Boolean))])
const filtered = computed(() => rows.value.filter((r) => !category.value || r.category === category.value))

function openDetail(row) {
  current.value = row
  drawer.value = true
}

async function load() {
  loading.value = true
  try {
    const [snapRes, schemaRes] = await Promise.allSettled([listFactorSnapshots(), getFactorSchema()])
    let list = []
    if (snapRes.status === 'fulfilled') list = unwrapList(snapRes.value)
    if (!list.length && schemaRes.status === 'fulfilled') {
      const data = unwrap(schemaRes.value)
      list = data.factors || data.items || unwrapList(schemaRes.value)
    }
    if (list.length) {
      rows.value = normalize(list)
      usingStub.value = false
    } else {
      rows.value = stubFactors()
      usingStub.value = true
    }
  } catch {
    rows.value = stubFactors()
    usingStub.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.muted { color: var(--text-secondary); font-size: 13px; }
h4 { margin: 16px 0 8px; font-size: 14px; }
.ret-list { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
.ret-list span { margin-left: 8px; }
</style>
