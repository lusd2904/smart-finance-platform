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
import { getMarketIndexQuotes } from '@/api/market'
import { changeClass, fmtPct } from '@/utils/format'

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

async function loadQuotes() {
  try {
    const res = await getMarketIndexQuotes()
    quotes.value = (res.data && res.data.items) || []
  } catch {
    quotes.value = []
  }
}

defineExpose({ loadQuotes })

let pollTimer = null

function stopPollTimer() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
function startPollTimer() {
  stopPollTimer()
  pollTimer = setInterval(loadQuotes, 60 * 1000)
}
function handleVisibility() {
  if (document.visibilityState === 'visible') {
    if (!pollTimer) {
      loadQuotes()
      startPollTimer()
    }
  } else {
    stopPollTimer()
  }
}

onMounted(() => {
  loadQuotes()
  // 后端 30s 缓存，前端 60s 轮询错开；空列表整体不渲染（不开盘全隐藏）
  startPollTimer()
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibility)
  stopPollTimer()
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
