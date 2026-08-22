<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">行情快照</span>
        <span class="panel-sub">{{ sourceText }}</span>
      </div>
    </template>

    <template v-if="hasData">
      <div class="sub-title" v-if="indices.length">指数</div>
      <div class="quote-row" v-for="q in indices" :key="`i-${q.symbol}`" @click="goKline(q.symbol)">
        <div class="q-left">
          <span class="q-symbol">{{ q.symbol }}</span>
          <span class="q-name">{{ q.name }}</span>
        </div>
        <div class="q-right" :class="changeClass(q.changeRate)">
          <span class="q-price">{{ q.price ?? '--' }}</span>
          <span class="q-chg">{{ fmtChange(q.changeRate) }}</span>
        </div>
      </div>
      <div class="sub-title" v-if="quotes.length">看板标的</div>
      <div class="quote-row" v-for="q in quotes" :key="`q-${q.market}-${q.symbol}`" @click="goKline(q.symbol)">
        <div class="q-left">
          <span class="q-symbol">{{ q.symbol }}</span>
          <span class="q-name">{{ q.name }}</span>
        </div>
        <div class="q-right" :class="changeClass(q.changeRate)">
          <span class="q-price">{{ q.price ?? '--' }}</span>
          <span class="q-chg">{{ fmtChange(q.changeRate) }}</span>
        </div>
      </div>
    </template>
    <el-empty v-else :description="reason" :image-size="80">
      <el-button type="primary" @click="go('/market/heat')">去行情中心</el-button>
    </el-empty>
  </el-card>
</template>

<script setup name="DashQuoteBoard">
import { changeClass, fmtChange, sectionOk, sectionReason } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const hasData = computed(() => sectionOk(props.section))
const d = computed(() => (props.section && props.section.data) || {})
const indices = computed(() => d.value.indices || [])
const quotes = computed(() => d.value.quotes || [])
const reason = computed(() => sectionReason(props.section, '看板缓存尚未生成，请等待 jobs 预热'))
const sourceText = computed(() => {
  if (!hasData.value) return ''
  const src = d.value.source
  if (d.value.stale) return '数据滞后'
  if (src === 'cache') return '实时缓存'
  return ''
})

function go(path) {
  router.push(path).catch(() => {})
}

function goKline(symbol) {
  if (!symbol) return
  router.push({ path: '/market/kline', query: { symbol } }).catch(() => {})
}
</script>

<style scoped lang="scss">
.panel-card {
  border-radius: 14px;
  border: 1px solid var(--border-soft, #eef2ff);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
}

.panel-sub {
  font-size: 12px;
  color: #94a3b8;
}

.sub-title {
  font-size: 12px;
  color: #94a3b8;
  margin: 8px 0 4px;

  &:first-child {
    margin-top: 0;
  }
}

.quote-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;

  &:hover {
    background: var(--surface-hover, #eef2ff);
  }
}

.q-symbol {
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
  margin-right: 8px;
}

.q-name {
  font-size: 12px;
  color: #94a3b8;
}

.q-right {
  text-align: right;

  &.up {
    color: var(--stat-up, #dc2626);
  }

  &.down {
    color: var(--stat-down, #059669);
  }

  &.flat {
    color: var(--text-emphasis, #0f172a);
  }
}

.q-price {
  display: block;
  font-weight: 700;
  font-size: 14px;
}

.q-chg {
  font-size: 12px;
}
</style>
