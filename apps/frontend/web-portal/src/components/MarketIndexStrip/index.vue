<template>
  <div class="index-strip" aria-label="大盘指数">
    <button
      v-for="q in cards"
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

/** Same universe as market-read indexSpecs / old live strip. Always rendered. */
const INDEX_SPECS = [
  { symbol: 'usINX', name: '标普500', market: 'US' },
  { symbol: 'usIXIC', name: '纳斯达克', market: 'US' },
  { symbol: 'usDJI', name: '道琼斯', market: 'US' },
  { symbol: 'r_hkHSI', name: '恒生指数', market: 'HK' },
  { symbol: 'r_hkHSTECH', name: '恒生科技', market: 'HK' },
  { symbol: 'r_hkHSCEI', name: '恒生国企', market: 'HK' },
  { symbol: 'sh000001', name: '上证指数', market: 'CN' },
  { symbol: 'sz399006', name: '创业板指数', market: 'CN' },
  { symbol: 'sh000688', name: '科创板指数', market: 'CN' }
]

const live = ref([])

function normSym(v) {
  return String(v || '')
    .toUpperCase()
    .replace(/^(US|HK|SH|SZ)/, '')
    .replace(/[^A-Z0-9]/g, '')
}

function matchSpec(spec, q) {
  if (!q) return false
  if (q.name && q.name === spec.name) return true
  const a = normSym(spec.symbol)
  const b = normSym(q.symbol)
  if (a && b && (a === b || a.endsWith(b) || b.endsWith(a))) return true
  return false
}

const cards = computed(() => {
  const source = [...(props.seed || []), ...(live.value || [])]
  const used = new Set()
  const out = INDEX_SPECS.map((spec) => {
    const hit = source.find((q) => matchSpec(spec, q))
    if (hit) {
      used.add(hit)
      return { ...spec, ...hit, name: spec.name, market: spec.market, symbol: spec.symbol }
    }
    return { ...spec }
  })
  for (const q of live.value || []) {
    if (used.has(q)) continue
    if (INDEX_SPECS.some((spec) => matchSpec(spec, q))) continue
    if (q.name || q.symbol) out.push(q)
  }
  return out
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
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.index-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 10px !important;
  font-size: 13px;
  border: 0;
  text-align: left;
  cursor: pointer;
  color: inherit;
  min-width: 196px;
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
.idx-chg {
  margin-left: auto;
  font-style: normal;
  font-variant-numeric: tabular-nums;
}
</style>
