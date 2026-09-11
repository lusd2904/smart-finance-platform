<template>
  <div v-if="quotes.length" class="index-strip">
    <article v-for="q in quotes" :key="q.symbol || q.name" class="index-item glass-panel">
      <span class="idx-market">{{ marketLabel(q.market) }}</span>
      <span class="idx-name">{{ q.name }}</span>
      <strong class="idx-last numeric">{{ fmtPx(q.last ?? q.price) }}</strong>
      <em :class="changeClass(q.changePct ?? q.changeRate)">{{ fmtChange(q.changePct ?? q.changeRate) }}</em>
    </article>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getMarketIndexQuotes } from '@/api/market'
import { changeClass, fmtChange, fmtPx } from '@/utils/format'
import { unwrap, unwrapList } from '@/utils/list'

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

function applyPayload(res) {
  const raw = unwrap(res)
  const items = raw.items || raw.list || (Array.isArray(raw) ? raw : unwrapList(res))
  if (Array.isArray(items) && items.length) live.value = items
}

async function loadQuotes() {
  try {
    applyPayload(await getMarketIndexQuotes())
  } catch {
    /* keep current strip / seed */
  }
}

let timer = null
onMounted(() => {
  loadQuotes()
  timer = window.setInterval(loadQuotes, 15000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
watch(
  () => props.seed,
  () => {
    if (!live.value.length && props.seed?.length) {
      /* seed shown via computed */
    }
  }
)

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
