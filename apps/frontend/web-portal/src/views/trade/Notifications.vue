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

    <el-alert v-if="usingStub" title="STUB · stubNotifications" type="warning" show-icon :closable="false" />

    <div class="toolbar">
      <div class="chip-row">
        <button type="button" class="filter-chip" :class="{ active: readFilter === 'unread' }" @click="readFilter = 'unread'">未读</button>
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
      <el-input v-model="keyword" clearable placeholder="搜索标题 / 正文" style="width:220px" :prefix-icon="Search" />
    </div>

    <p class="summary-line">
      <span class="numeric">{{ filtered.length }}</span> 条
      <span class="dot">·</span>
      <span class="numeric">{{ unreadCount }}</span> 未读
    </p>

    <el-card shadow="never" class="glass-panel notifications-page">
      <div v-if="filtered.length" class="inbox">
        <article v-for="n in filtered" :key="n.id" class="inbox-item" :class="{ unread: !n.read }">
          <i class="unread-dot" aria-hidden="true" />
          <div class="inbox-copy">
            <div class="inbox-head">
              <span class="type-tag" :class="`is-${typeKey(n)}`">{{ typeLabel(n) }}</span>
              <time class="numeric muted">{{ timeText(n) }}</time>
            </div>
            <strong>{{ n.title }}</strong>
            <p>{{ n.content || n.body || '' }}</p>
          </div>
          <el-button v-if="!n.read" link type="primary" @click="mark(n)">标为已读</el-button>
        </article>
      </div>
      <el-empty v-else description="暂无通知" :image-size="72" />
    </el-card>

    <template #legend>
      <span>全页收件箱 · 非 Header 铃铛 · GET /trade/notifications · POST /trade/notifications/read</span>
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
  { key: '', label: '全部' },
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
  if (c === 'trade' || c === '交易') return 'trade'
  if (c === 'risk' || c === '风控') return 'risk'
  return 'system'
}
function typeLabel(n) {
  return { trade: '交易', risk: '风控', system: '系统' }[typeKey(n)]
}
function timeText(n) {
  const raw = String(n.createTime || n.time || '').trim()
  if (!raw) return '--'
  return raw.length > 8 ? raw.slice(-8) : raw
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
    list.value = rows
    usingStub.value = false
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
  list.value = list.value.map((n) => ({ ...n, read: true }))
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
  justify-content: space-between;
  margin-bottom: 8px;
}
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.summary-line { margin: 0 0 10px; color: var(--text-secondary); font-size: 13px; }
.summary-line .dot { margin: 0 6px; opacity: 0.6; }
.inbox { display: grid; }
.inbox-item {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 10px;
  align-items: start;
  padding: 12px 4px;
  border-bottom: 1px solid var(--control-border);
}
.inbox-item:last-child { border-bottom: 0; }
.unread-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: transparent;
}
.inbox-item.unread .unread-dot { background: var(--accent); }
.inbox-item.unread strong { color: var(--text-emphasis); }
.inbox-copy p { margin: 4px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.6; }
.inbox-head { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.muted { color: var(--text-secondary); font-size: 12px; }
.type-tag {
  display: inline-flex;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: color-mix(in srgb, var(--accent) var(--chip-fill), transparent);
  color: var(--accent);
}
.type-tag.is-trade {
  color: var(--order-buy-solid);
  background: color-mix(in srgb, var(--stat-up) var(--chip-fill), transparent);
}
.type-tag.is-risk {
  color: #d97706;
  background: color-mix(in srgb, #f59e0b var(--chip-fill), transparent);
}
</style>
