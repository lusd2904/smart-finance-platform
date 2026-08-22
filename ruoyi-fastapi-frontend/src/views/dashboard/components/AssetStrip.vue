<template>
  <el-row :gutter="16" class="asset-strip">
    <el-col :xs="12" :sm="6" v-for="card in cards" :key="card.key">
      <div class="stat-card" @click="go(card.path)">
        <div class="stat-icon">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.cls">{{ card.value }}</div>
        </div>
      </div>
    </el-col>
  </el-row>
</template>

<script setup name="DashAssetStrip">
import { changeClass, fmtAmount } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const denied = computed(() => props.section && props.section.reason === 'denied')
const d = computed(() => (props.section && props.section.data) || {})

function fmtMoney(val) {
  if (!d.value.configured) return '--'
  return fmtAmount(val)
}

const cards = computed(() => {
  if (denied.value || !props.section) {
    return [
      { key: 'net', label: '总净值', value: '未授权', icon: 'Wallet', cls: '', path: '' },
      { key: 'cash', label: '可用资金', value: '--', icon: 'Coin', cls: '', path: '' },
      { key: 'pos', label: '持仓数', value: '--', icon: 'Grid', cls: '', path: '' },
      { key: 'pnl', label: '浮动盈亏', value: '--', icon: 'TrendCharts', cls: 'flat', path: '' }
    ]
  }
  const configured = d.value.configured
  return [
    {
      key: 'net',
      label: configured ? `总净值(${d.value.currency || '--'})` : '总净值',
      value: configured ? fmtMoney(d.value.netAssets) : '未配置',
      icon: 'Wallet',
      cls: '',
      path: '/quant/overview'
    },
    {
      key: 'cash',
      label: '可用资金',
      value: configured ? fmtMoney(d.value.availableCash) : '--',
      icon: 'Coin',
      cls: '',
      path: '/quant/overview'
    },
    {
      key: 'pos',
      label: '持仓数',
      value: String(d.value.positionCount ?? 0),
      icon: 'Grid',
      cls: '',
      path: '/trade/trading'
    },
    {
      key: 'pnl',
      label: '浮动盈亏',
      value: configured ? fmtMoney(d.value.totalUnrealizedPnl) : '--',
      icon: 'TrendCharts',
      cls: changeClass(d.value.totalUnrealizedPnl),
      path: '/trade/trading'
    }
  ]
})

function go(path) {
  if (path) router.push(path).catch(() => {})
}
</script>

<style scoped lang="scss">
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  margin-bottom: 12px;
  border-radius: 14px;
  background: var(--surface-card, #fff);
  border: 1px solid var(--border-soft, #eef2ff);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-glow);
  }
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-card .stat-icon {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
}

.stat-card:nth-child(2n) .stat-icon {
  background: linear-gradient(135deg, #0ea5e9, #38bdf8);
}

.stat-label {
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-emphasis, #0f172a);
  line-height: 1.3;

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
</style>
