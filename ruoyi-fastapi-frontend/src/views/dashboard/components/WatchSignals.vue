<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">自选信号</span>
        <span v-if="d.count" class="stance-badges">
          <el-tag size="small" type="danger" effect="plain">多 {{ d.bullish }}</el-tag>
          <el-tag size="small" type="success" effect="plain">空 {{ d.bearish }}</el-tag>
          <el-tag size="small" type="info" effect="plain">中 {{ d.neutral }}</el-tag>
        </span>
        <el-button link type="primary" @click="go('/market/watchlist')">管理</el-button>
      </div>
    </template>

    <template v-if="hasData && signals.length">
      <div class="signal-row" v-for="s in signals" :key="`${s.market}:${s.symbol}`" @click="goKline(s)">
        <div class="sig-left">
          <span class="sig-symbol">{{ s.symbol }}</span>
          <span class="sig-name">{{ s.name }}</span>
          <el-tag
            v-if="s.stance"
            size="small"
            :type="stanceType(s.stance)"
            effect="light"
            class="sig-stance"
          >{{ s.stance }}</el-tag>
        </div>
        <div class="sig-right">
          <span class="sig-last" :class="changeClass(s.changeRate)">{{ s.last ?? '--' }}</span>
          <span class="sig-chg" :class="changeClass(s.changeRate)">{{ fmtChange(s.changeRate) }}</span>
        </div>
      </div>
      <div v-if="!d.aiAvailable" class="ai-hint">AI 模型未配置，信号为技术指标兜底结果</div>
    </template>
    <el-empty v-else :description="reason" :image-size="80">
      <el-button type="primary" @click="go('/market/watchlist')">去添加自选</el-button>
    </el-empty>
  </el-card>
</template>

<script setup name="DashWatchSignals">
import { changeClass, fmtChange, sectionOk, sectionReason } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const denied = computed(() => props.section && props.section.reason === 'denied')
const d = computed(() => (props.section && props.section.data) || {})
const hasData = computed(() => sectionOk(props.section))
const signals = computed(() => d.value.signals || [])
const reason = computed(() =>
  denied.value ? '无自选查看权限' : sectionReason(props.section, '暂无启用中的自选标的')
)

function stanceType(stance) {
  if (stance === '偏多') return 'danger'
  if (stance === '偏空') return 'success'
  return 'info'
}

function go(path) {
  router.push(path).catch(() => {})
}

function goKline(signal) {
  router.push({ path: '/market/kline', query: { symbol: signal.symbol } }).catch(() => {})
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
  gap: 8px;
  flex-wrap: wrap;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-emphasis, #0f172a);
}

.stance-badges {
  display: inline-flex;
  gap: 4px;
  margin-left: auto;
  margin-right: 8px;
}

.signal-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #eef2ff);
  margin-bottom: 8px;
  cursor: pointer;

  &:hover {
    background: var(--surface-hover, #eef2ff);
  }
}

.sig-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.sig-symbol {
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
}

.sig-name {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sig-right {
  text-align: right;
}

.sig-last {
  display: block;
  font-weight: 700;
}

.sig-chg {
  font-size: 12px;
}

.up {
  color: var(--stat-up, #dc2626);
}

.down {
  color: var(--stat-down, #059669);
}

.flat {
  color: var(--text-emphasis, #0f172a);
}

.ai-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #b45309;
}
</style>
