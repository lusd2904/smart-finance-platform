<template>
  <Teleport to="body">
    <div v-if="modelValue" class="m-search">
      <header class="m-search__bar">
        <button type="button" class="m-back" @click="close">‹</button>
        <input
          ref="inputEl"
          v-model="keyword"
          type="search"
          enterkeyhint="search"
          placeholder="搜索代码 / 名称"
        />
      </header>
      <EmptyState v-if="error && !rows.length" :message="error" retry @retry="searchNow" />
      <EmptyState v-else-if="!keyword.trim()" message="输入代码或名称，加入自选" />
      <EmptyState v-else-if="!loading && !rows.length" message="没有匹配标的" />
      <div v-for="row in rows" :key="(row.symbol || '') + (row.market || '')" class="m-search__row">
        <button type="button" class="m-search__main" @click="$emit('open', row)">
          <div class="m-search__name">{{ row.name || row.symbol }}</div>
          <div class="m-search__sub">{{ row.symbol }} · {{ marketLabel(row.market) }}</div>
        </button>
        <button
          type="button"
          class="m-search__add"
          :disabled="busyKey === rowKey(row) || already(row)"
          @click="beginAdd(row)"
        >{{ already(row) ? '已加' : '+' }}</button>
      </div>
      <Skeleton v-if="loading && !rows.length" :rows="6" />
      <div v-if="toast" class="m-toast">{{ toast }}</div>
      <GroupPickSheet
        v-model="groupOpen"
        :groups="groups"
        allow-skip
        @pick="finishAdd"
      />
    </div>
  </Teleport>
</template>

<script setup>
import { listInstrumentUniverse, addMarketWatchlist } from '@/api/market'
import EmptyState from './EmptyState.vue'
import Skeleton from './Skeleton.vue'
import GroupPickSheet from './GroupPickSheet.vue'
import { unwrapRows, str } from '../utils/payload'
import { marketLabel } from '../utils/format'
import { inferMarket } from '../utils/ticketQty'
import { isWatchlisted, noteFromGroup } from '../utils/watchlist'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  groups: { type: Array, default: () => [] },
  watchItems: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'added', 'open'])

const keyword = ref('')
const rows = ref([])
const loading = ref(false)
const error = ref('')
const toast = ref('')
const busyKey = ref('')
const groupOpen = ref(false)
const pending = ref(null)
const inputEl = ref(null)
let timer = 0
let seq = 0

function rowKey(row) {
  return `${String(row.symbol || '').toUpperCase()}|${String(row.market || '').toUpperCase()}`
}

function already(row) {
  return isWatchlisted(props.watchItems, row.symbol, row.market || inferMarket(row.symbol, 'US'))
}

function close() {
  emit('update:modelValue', false)
}

async function searchNow() {
  const kw = keyword.value.trim()
  if (!kw) {
    rows.value = []
    error.value = ''
    return
  }
  const ticket = ++seq
  loading.value = true
  error.value = ''
  try {
    const res = await listInstrumentUniverse({ keyword: kw, pageNum: 1, pageSize: 50 })
    if (ticket !== seq) return
    rows.value = unwrapRows(res).map((r) => ({
      ...r,
      symbol: str(r.symbol),
      name: str(r.name || r.symbolName || r.symbol),
      market: str(r.market) || inferMarket(r.symbol, 'US')
    }))
  } catch (e) {
    if (ticket !== seq) return
    error.value = (e && e.message) || '搜索失败'
    rows.value = []
  } finally {
    if (ticket === seq) loading.value = false
  }
}

function scheduleSearch() {
  clearTimeout(timer)
  timer = setTimeout(searchNow, 300)
}

function beginAdd(row) {
  if (already(row) || busyKey.value) return
  pending.value = row
  groupOpen.value = true
}

async function finishAdd(note) {
  const row = pending.value
  pending.value = null
  if (!row) return
  busyKey.value = rowKey(row)
  try {
    await addMarketWatchlist({
      symbol: row.symbol,
      market: row.market || inferMarket(row.symbol, 'US'),
      note: noteFromGroup(note)
    })
    toast.value = note ? `已加入「${note}」` : '已加入自选'
    emit('added', { ...row, note: noteFromGroup(note) })
    setTimeout(() => { toast.value = '' }, 1600)
  } catch (e) {
    toast.value = (e && e.message) || '加入失败'
    setTimeout(() => { toast.value = '' }, 2000)
  } finally {
    busyKey.value = ''
  }
}

watch(keyword, scheduleSearch)

watch(() => props.modelValue, (open) => {
  if (open) {
    keyword.value = ''
    rows.value = []
    error.value = ''
    nextTick(() => inputEl.value && inputEl.value.focus())
  } else {
    clearTimeout(timer)
  }
})
</script>

<style scoped lang="scss">
.m-search {
  position: fixed;
  inset: 0;
  z-index: 86;
  display: flex;
  flex-direction: column;
  background: #f4f5f7;
  padding-top: env(safe-area-inset-top, 0px);
}
.m-search__bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #ececef;
}
.m-search__bar input {
  flex: 1;
  height: 36px;
  border: 0;
  border-radius: 8px;
  background: #f4f5f7;
  padding: 0 12px;
  font-size: 15px;
}
.m-back {
  width: 36px;
  height: 36px;
  border: 0;
  background: transparent;
  font-size: 26px;
  line-height: 1;
}
.m-search__row {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #f0f1f3;
}
.m-search__main {
  flex: 1;
  min-width: 0;
  padding: 12px 16px;
  border: 0;
  background: transparent;
  text-align: left;
}
.m-search__name {
  font-weight: 700;
  font-size: 15px;
}
.m-search__sub {
  margin-top: 2px;
  color: #8b8d98;
  font-size: 11px;
}
.m-search__add {
  width: 48px;
  height: 36px;
  margin-right: 12px;
  border: 0;
  border-radius: 8px;
  background: #111827;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
}
.m-search__add:disabled {
  background: #eceef2;
  color: #8b8d98;
}
</style>
