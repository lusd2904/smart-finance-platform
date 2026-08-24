<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">三市场热度</span>
        <el-button link type="primary" @click="go('/market/heat')">行情中心</el-button>
      </div>
    </template>

    <div v-if="hasData" class="heat-grid">
      <div v-for="m in rows" :key="m.market" class="heat-box" :class="{ empty: !m.data }" @click="go(`/market/heat?market=${m.market}`)">
        <template v-if="m.data">
          <div class="heat-head">
            <span class="heat-market">{{ m.label }}</span>
            <span class="heat-date">{{ m.data.tradeDate }}</span>
          </div>
          <div class="heat-index">
            <span class="idx-name">{{ m.data.indexName }}</span>
            <span class="idx-chg" :class="changeClass(m.data.indexChangePct)">{{ fmtChange(m.data.indexChangePct) }}</span>
          </div>
          <div class="heat-ad">
            <span class="ad-up">涨 {{ m.data.advanceCount ?? '-' }}</span>
            <span class="ad-flat">平 {{ m.data.flatCount ?? '-' }}</span>
            <span class="ad-down">跌 {{ m.data.declineCount ?? '-' }}</span>
          </div>
          <div class="heat-foot">
            <span class="turnover">成交 {{ fmtAmount(m.data.totalTurnover, m.data.currency) }}</span>
            <span class="score" v-if="m.data.heatScore != null">热度 {{ m.data.heatScore }}</span>
          </div>
        </template>
        <template v-else>
          <div class="heat-market">{{ m.label }}</div>
          <el-empty :image-size="48" description="暂无快照" />
        </template>
      </div>
    </div>
    <el-empty v-else :description="reason" :image-size="80" />
  </el-card>
</template>

<script setup name="DashHeatSummary">
import { changeClass, fmtAmount, fmtChange, sectionOk, sectionReason } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const hasData = computed(() => sectionOk(props.section))
const reason = computed(() => sectionReason(props.section, '暂无热度快照，收盘任务完成后写入'))
const rows = computed(() => {
  const data = (props.section && props.section.data) || {}
  return [
    { market: 'US', label: '美股', data: data.US },
    { market: 'HK', label: '港股', data: data.HK },
    { market: 'CN', label: 'A股', data: data.CN }
  ]
})

function go(path) {
  router.push(path).catch(() => {})
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

.heat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.heat-box {
  padding: 12px;
  border-radius: 12px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #e2e8f0);
  cursor: pointer;
  transition: background 0.15s ease;
  min-height: 118px;

  &:hover {
    background: var(--surface-hover, #eef2ff);
  }

  &.empty {
    cursor: default;
  }
}

.heat-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.heat-market {
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
}

.heat-date {
  font-size: 11px;
  color: #94a3b8;
}

.heat-index {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 6px;
}

.idx-name {
  font-size: 12px;
  color: #64748b;
}

.idx-chg {
  font-size: 18px;
  font-weight: 700;

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

.heat-ad {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  font-size: 12px;
}

.ad-up {
  color: var(--stat-up, #dc2626);
}

.ad-down {
  color: var(--stat-down, #059669);
}

.ad-flat {
  color: #94a3b8;
}

.heat-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 768px) {
  .heat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
