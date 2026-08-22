<template>
  <div v-if="quotes.length" class="index-strip">
    <div v-for="q in quotes" :key="q.symbol" class="index-item">
      <span class="idx-name">{{ q.name }}</span>
      <span class="idx-last">{{ fmtLast(q.last) }}</span>
      <span class="idx-chg" :class="chgCls(q.changePct)">
        {{ q.changePct !== null && q.changePct !== undefined ? fmtChg(q.changePct) : '--' }}
      </span>
    </div>
  </div>
</template>

<script setup name="SentimentIndexStrip">
import { getMarketIndexQuotes } from '@/api/market';

const quotes = ref([]);

function fmtLast(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--';
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtChg(v) {
  const n = Number(v);
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}

/** 中国习惯：涨红跌绿 */
function chgCls(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'flat';
  return n > 0 ? 'up' : 'down';
}

async function loadQuotes() {
  try {
    const res = await getMarketIndexQuotes();
    quotes.value = (res.data && res.data.items) || [];
  } catch {
    quotes.value = [];
  }
}

defineExpose({ loadQuotes });

let pollTimer = null;

onMounted(() => {
  loadQuotes();
  // 指数条独立 60s 轮询，与后端 30s 缓存错开；无数据时组件整体不渲染
  pollTimer = setInterval(loadQuotes, 60 * 1000);
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<style lang="scss" scoped>
.index-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #ebeef5);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.index-item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 8px;
  background: var(--surface-muted, #f8fafc);

  .idx-name {
    font-size: 13px;
    color: var(--text-secondary, #606266);
  }

  .idx-last {
    font-size: 14px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-emphasis, #303133);
  }

  .idx-chg {
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;

    &.up {
      color: #f56c6c;
    }

    &.down {
      color: #67c23a;
    }

    &.flat {
      color: #909399;
    }
  }
}
</style>
