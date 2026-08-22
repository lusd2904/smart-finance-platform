<template>
  <el-card shadow="never" class="panel-card health-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">平台运行状态</span>
        <el-tag size="small" :type="overallType" effect="plain">{{ overallText }}</el-tag>
      </div>
    </template>

    <template v-if="hasData">
      <div class="health-grid">
        <div class="health-item">
          <div class="health-label">K线覆盖率</div>
          <div class="health-value" :class="coverageCls">{{ coverageText }}</div>
          <div class="health-sub" v-if="d.coverage">{{ d.coverage.covered }}/{{ d.coverage.total }} 标的已覆盖</div>
        </div>
        <div class="health-item">
          <div class="health-label">24h 任务执行</div>
          <div class="health-value" :class="jobsCls">{{ jobsText }}</div>
          <div class="health-sub" v-if="lastJobText">最近：{{ lastJobText }}</div>
        </div>
      </div>
    </template>
    <el-empty v-else :description="reason" :image-size="60" />
  </el-card>
</template>

<script setup name="DashSystemHealth">
import { sectionOk, sectionReason } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const denied = computed(() => props.section && props.section.reason === 'denied')
const hasData = computed(() => sectionOk(props.section))
const d = computed(() => (props.section && props.section.data) || {})
const reason = computed(() => (denied.value ? '无监控权限' : sectionReason(props.section, '暂无运行数据')))

const coveragePct = computed(() => {
  const c = d.value.coverage
  return c && Number.isFinite(Number(c.coveragePct)) ? Number(c.coveragePct) : null
})
const coverageText = computed(() => (coveragePct.value === null ? '--' : `${coveragePct.value}%`))
const coverageCls = computed(() => {
  if (coveragePct.value === null) return ''
  if (coveragePct.value >= 90) return 'good'
  if (coveragePct.value >= 60) return 'warn'
  return 'bad'
})

const failed = computed(() => (d.value.jobs24h || {}).failed ?? null)
const total = computed(() => (d.value.jobs24h || {}).total ?? null)
const jobsText = computed(() => {
  if (total.value === null) return '--'
  const f = failed.value || 0
  return f > 0 ? `${total.value} 次 / 失败 ${f}` : `${total.value} 次全部成功`
})
const jobsCls = computed(() => ((failed.value || 0) > 0 ? 'warn' : 'good'))

const lastJobText = computed(() => {
  const j = d.value.lastJob
  if (!j) return ''
  const status = j.status === '1' ? '失败' : '正常'
  return `${j.jobName} · ${status} · ${j.createTime}`
})

const overallType = computed(() => {
  if (!hasData.value) return 'info'
  const covBad = coveragePct.value !== null && coveragePct.value < 60
  const jobBad = (failed.value || 0) > 0
  if (covBad || jobBad) return 'warning'
  return 'success'
})
const overallText = computed(() => {
  if (!hasData.value) return '未知'
  return overallType.value === 'success' ? '运行正常' : '需要关注'
})
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

.health-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.health-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #e2e8f0);
}

.health-label {
  font-size: 12px;
  color: #64748b;
}

.health-value {
  font-size: 18px;
  font-weight: 700;
  margin-top: 4px;

  &.good {
    color: var(--stat-down, #059669);
  }

  &.warn {
    color: #b45309;
  }

  &.bad {
    color: var(--stat-up, #dc2626);
  }
}

.health-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
