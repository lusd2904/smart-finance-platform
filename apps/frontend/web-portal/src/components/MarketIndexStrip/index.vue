<template>
  <div v-if="quotes.length" class="index-strip">
    <button
      v-for="q in quotes"
      :key="q.symbol || q.name"
      type="button"
      class="index-item glass-panel"
      :title="`${q.name} · ${q.quoteTime || ''}`"
      @click="$emit('select', q)"
    >
      <span class="idx-market">{{ marketLabel(q.market) }}</span>
      <span class="idx-name">{{ q.name }}</span>
      <strong class="idx-last numeric">{{ fmtPx(q.last ?? q.price) }}</strong>
      <em class="idx-chg" :class="changeClass(q.changePct ?? q.changeRate)">{{ fmtChange(q.changePct ?? q.changeRate) }}</em>
    </button>
  </div>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { bindMarketQuotesSocket } from '@/composables/useMarketQuotesWs'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'

defineEmits(['select'])

const props = defineProps({
  seed: { type: Array, default: () => [] }
})

const live = ref([])

const quotes = computed(() => {
  const byM = { US: null, HK: null, CN: null }
  const source = live.value.length ? live.value : props.seed
  for (const q of source || []) {
    const m = q.market === 'A' ? 'CN' : q.market
    if (byM[m] == null) byM[m] = q
  }
  return ['US', 'HK', 'CN'].map((m) => byM[m]).filter(Boolean)
})

function marketLabel(market) {
  if (market === 'US') return '美'
  if (market === 'HK') return '港'
  if (market === 'CN' || market === 'A') return 'A'
  return market || '--'
}

function applyQuotes(data) {
  const items = (data && data.items) || []
  if (Array.isArray(items) && items.length) live.value = items
}

const socket = bindMarketQuotesSocket({ onData: applyQuotes, intervalSec: 15 })

function loadQuotes() {
  socket.reload()
}

function handleVisibility() {
  if (document.visibilityState === 'visible') socket.start()
  else socket.stop()
}

onMounted(() => {
  socket.start()
  document.addEventListener('visibilitychange', handleVisibility)
})
onActivated(() => socket.start())
onDeactivated(() => socket.stop())
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibility)
  socket.stop()
})

defineExpose({ loadQuotes })
</script>

<style scoped>
.index-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.index-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 10px !important;
  font-size: 13px;
  border: 0;
  width: 100%;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.index-item em {
  margin-left: auto;
  font-style: normal;
  font-variant-numeric: tabular-nums;
}
.idx-market {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent, #6366f1);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border-radius: 4px;
  padding: 1px 5px;
}
.idx-name {
  color: var(--text-secondary);
}
.idx-last {
  font-size: 14px;
}
@media (max-width: 900px) {
  .index-strip {
    grid-template-columns: 1fr;
  }
}
</style>
