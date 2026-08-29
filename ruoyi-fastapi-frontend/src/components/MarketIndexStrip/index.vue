<template>
  <div v-if="quotes.length" class="index-strip">
    <button
      v-for="q in quotes"
      :key="q.symbol"
      type="button"
      class="index-item"
      :title="`${q.name} · ${q.quoteTime || ''}`"
      @click="$emit('select', q)"
    >
      <span class="idx-market">{{ marketLabel(q.market) }}</span>
      <span class="idx-name">{{ q.name }}</span>
      <span class="idx-last">{{ fmtNum(q.last) }}</span>
      <span class="idx-chg" :class="changeClass(q.changePct)">{{ fmtPct(q.changePct) }}</span>
    </button>
  </div>
</template>

<script setup name="MarketIndexStrip">
import { changeClass, fmtPct } from '@/utils/format'
import { bindMarketQuotesSocket } from '@/composables/useMarketQuotesWs'

defineEmits(['select'])

const quotes = ref([])

const MARKET_LABELS = { US: '美', HK: '港', CN: 'A' }

function marketLabel(market) {
  return MARKET_LABELS[market] || ''
}

function fmtNum(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function applyQuotes(data) {
  quotes.value = (data && data.items) || []
}

const socket = bindMarketQuotesSocket({ onData: applyQuotes, intervalSec: 15 })

function loadQuotes() {
  socket.reload()
}

defineExpose({ loadQuotes })

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
</script>

<style scoped lang="scss">
.index-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
}

.index-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 9px;
  border: none;
  background: var(--surface-muted, #f8fafc);
  cursor: pointer;
  transition:
    background 0.15s ease,
    transform 0.15s ease;

  &:hover {
    background: var(--surface-hover, #eef2ff);
    transform: translateY(-1px);
  }

  .idx-market {
    font-size: 11px;
    font-weight: 700;
    color: var(--accent, #6366f1);
    background: rgba(99, 102, 241, 0.1);
    border-radius: 5px;
    padding: 1px 5px;
  }

  .idx-name {
    font-size: 13px;
    color: var(--text-secondary, #606266);
  }

  .idx-last {
    font-size: 14px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--text-emphasis, #303133);
  }

  .idx-chg {
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;

    &.up {
      color: var(--stat-up, #dc2626);
    }

    &.down {
      color: var(--stat-down, #059669);
    }

    &.flat {
      color: var(--text-muted, #909399);
    }
  }
}
</style>
