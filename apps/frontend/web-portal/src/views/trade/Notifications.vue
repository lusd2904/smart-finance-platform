<template>
  <PageFrame
    title="通知中心"
    subtitle="全页收件箱 · 未读 / 类型筛选 · 全部标已读 · 对齐 /trade/notifications"
    badge="「通知中心 /trade/notifications」"
    :loading="loading"
  >
    <template #actions>
      <el-button @click="markAll">全部标已读</el-button>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <div class="toolbar">
      <div class="chip-row">
        <button type="button" class="filter-chip" :class="{ active: readFilter === 'unread' }" @click="readFilter = 'unread'">未读 ({{ unreadCount }})</button>
        <button type="button" class="filter-chip" :class="{ active: readFilter === 'all' }" @click="readFilter = 'all'">全部</button>
      </div>
      <div class="chip-row">
        <button
          v-for="tab in typeTabs"
          :key="tab.key"
          type="button"
          class="filter-chip"
          :class="{ active: typeFilter === tab.key }"
          @click="typeFilter = tab.key"
        >{{ tab.label }}</button>
      </div>
    </div>
    <el-input v-model="keyword" clearable placeholder="标题 / 内容" :prefix-icon="Search" class="search-wide" />

    <el-card shadow="never" class="glass-panel notifications-page">
      <template #header>
        <div class="list-head">
          <h3>通知列表</h3>
          <span class="muted">类型 · 时间 · 标题 · 标记已读</span>
        </div>
      </template>
      <div v-if="filtered.length" class="inbox">
        <article v-for="n in filtered" :key="n.id" class="inbox-item" :class="{ unread: !n.read }">
          <div class="inbox-copy">
            <strong>{{ n.title }}</strong>
            <p>{{ n.content || n.body || '' }}</p>
            <div class="inbox-meta">
              <span class="type-tag" :class="`is-${kindKey(n)}`">{{ kindLabel(n) }}</span>
              <span class="cat-pill">{{ typeKey(n) }}</span>
              <time class="numeric muted">{{ timeText(n) }}</time>
            </div>
          </div>
          <el-button v-if="!n.read" @click="mark(n)">标已读</el-button>
          <span v-else class="read-label">已读</span>
        </article>
      </div>
      <el-empty v-else description="暂无通知" :image-size="72" />
    </el-card>

    <template #legend>
      <span>全页收件箱 · 非 Header 铃铛 · GET /trade/notifications · POST /trade/notifications/read · stub 回退</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { listNotifications, readNotifications } from '@/api/trade'
import { unwrapList } from '@/utils/list'
import { stubNotifications } from '@/utils/stubs'

const TYPE_TABS = [
  { key: '', label: '全部类型' },
  { key: 'trade', label: '交易' },
  { key: 'risk', label: '风控' },
  { key: 'system', label: '系统' }
]

const loading = ref(false)
const usingStub = ref(false)
const list = ref([])
const readFilter = ref('unread')
const typeFilter = ref('')
const keyword = ref('')
const typeTabs = TYPE_TABS

function typeKey(n) {
  const c = String(n.category || n.type || '').toLowerCase()
  if (c === 'trade' || c === '交易' || c === 'order' || c === 'fill') return 'trade'
  if (c === 'risk' || c === '风控') return 'risk'
  return 'system'
}
function kindKey(n) {
  if (n.tag === '成交' || n.kind === 'fill' || String(n.title || '').includes('成交')) return 'fill'
  if (n.tag === '委托' || n.kind === 'order' || String(n.title || '').includes('委托')) return 'order'
  if (typeKey(n) === 'risk') return 'risk'
  return 'system'
}
function kindLabel(n) {
  if (n.tag) return n.tag
  return { order: '委托', fill: '成交', risk: '风控', system: '系统' }[kindKey(n)]
}
function timeText(n) {
  const raw = String(n.createTime || n.time || '').trim()
  if (!raw) return '--'
  if (raw.includes('昨日')) return raw
  return raw.length >= 16 ? raw.slice(11, 16) : raw.length > 5 ? raw.slice(-5) : raw
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return list.value.filter((n) => {
    const readOk = readFilter.value === 'all' || !n.read
    const typeOk = !typeFilter.value || typeKey(n) === typeFilter.value
    const text = `${n.title || ''} ${n.content || n.body || ''}`.toLowerCase()
    return readOk && typeOk && (!kw || text.includes(kw))
  })
})
const unreadCount = computed(() => list.value.filter((n) => !n.read).length)

function applyStub() {
  usingStub.value = true
  list.value = stubNotifications()
}

async function load() {
  loading.value = true
  try {
    const res = await listNotifications(80)
    const rows = Array.isArray(res.data) ? res.data : unwrapList(res)
    if (rows.length) {
      list.value = rows
      usingStub.value = false
    } else applyStub()
  } catch {
    applyStub()
  } finally {
    loading.value = false
  }
}

async function mark(n) {
  if (!usingStub.value) {
    try { await readNotifications(n.id) } catch { /* keep local */ }
  }
  n.read = true
}

async function markAll() {
  if (!usingStub.value) {
    try { await readNotifications() } catch { /* keep local */ }
  }
  list.value = list.value.map((item) => ({ ...item, read: true }))
  ElMessage.success('已全部标为已读')
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.search-wide { width: 100%; margin-bottom: 12px; }
.list-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
h3 { margin: 0; font-size: 15px; }
.inbox { display: grid; }
.inbox-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: start;
  padding: 14px 4px;
  border-bottom: 1px solid var(--control-border);
}
.inbox-item:last-child { border-bottom: 0; }
.inbox-item.unread strong { color: var(--text-emphasis); }
.inbox-copy p { margin: 6px 0 8px; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.inbox-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.muted { color: var(--text-secondary); font-size: 12px; }
.read-label { color: var(--text-secondary); font-size: 12px; padding-top: 4px; }
.type-tag,
.cat-pill {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.type-tag.is-order {
  color: var(--accent);
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
}
.type-tag.is-fill {
  color: var(--order-sell-solid);
  background: color-mix(in srgb, var(--stat-down) var(--chip-fill), transparent);
}
.type-tag.is-risk {
  color: #d97706;
  background: color-mix(in srgb, #f59e0b var(--chip-fill), transparent);
}
.type-tag.is-system {
  color: #0d9488;
  background: color-mix(in srgb, #14b8a6 var(--chip-fill), transparent);
}
.cat-pill {
  font-weight: 600;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
  border: 1px solid var(--control-border);
}
</style>
