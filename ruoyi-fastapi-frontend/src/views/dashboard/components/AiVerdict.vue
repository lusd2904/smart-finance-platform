<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">最新舆情研判</span>
        <el-button link type="primary" @click="go('/sentiment/analysis')">查看全部</el-button>
      </div>
    </template>

    <template v-if="latest.summary">
      <div class="analysis-meta">
        <el-tag size="small" effect="plain">{{ latest.modelName || 'AI' }}</el-tag>
        <span class="meta-time">{{ latest.createTime || '--' }}</span>
      </div>
      <div class="analysis-summary">{{ latest.summary }}</div>
      <el-row :gutter="12" class="score-row">
        <el-col :span="8" v-for="m in marketScores" :key="m.key">
          <div class="score-box" :class="m.cls">
            <div class="score-name">{{ m.name }}</div>
            <div class="score-val">{{ m.score }}</div>
            <div class="score-dir">{{ m.direction || '暂无' }}</div>
          </div>
        </el-col>
      </el-row>
      <div class="risk-block" v-if="latest.riskEvents">
        <div class="risk-title">风险提示</div>
        <div class="risk-text">{{ latest.riskEvents }}</div>
      </div>
    </template>
    <el-empty v-else description="暂无舆情分析，可先采集资讯再执行分析" :image-size="90">
      <el-button type="primary" @click="go('/sentiment/dashboard')">去舆情大盘</el-button>
    </el-empty>
  </el-card>
</template>

<script setup name="DashAiVerdict">
import { sentimentIndexTo100 } from '@/utils/sentimentScore'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const latest = computed(() => ((props.section && props.section.data) || {}).latestAnalysis || {})

const marketScores = computed(() => {
  const a = latest.value || {}
  const pack = (key, name, direction, score) => {
    const dir = direction || ''
    let cls = 'neutral'
    if (dir.includes('多')) cls = 'bull'
    else if (dir.includes('空')) cls = 'bear'
    return { key, name, direction: dir || '--', score: score === 0 || score ? score : '--', cls }
  }
  return [pack('us', '美股', a.usDirection, sentimentIndexTo100(a.usScore)), pack('hk', '港股', a.hkDirection, sentimentIndexTo100(a.hkScore)), pack('a', 'A股', a.aDirection, sentimentIndexTo100(a.aScore))]
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

.analysis-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.meta-time {
  color: #94a3b8;
  font-size: 12px;
}

.analysis-summary {
  line-height: 1.7;
  color: #334155;
  margin-bottom: 14px;
  white-space: pre-wrap;
}

.score-row {
  margin-bottom: 8px;
}

.score-box {
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  background: var(--surface-muted, #f8fafc);
  border: 1px solid var(--border-soft, #e2e8f0);
  margin-bottom: 8px;

  &.bull {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.35);

    .score-val {
      color: var(--stat-down, #059669);
    }
  }

  &.bear {
    background: rgba(239, 68, 68, 0.12);
    border-color: rgba(239, 68, 68, 0.35);

    .score-val {
      color: var(--stat-up, #dc2626);
    }
  }

  &.neutral .score-val {
    color: var(--text-secondary, #475569);
  }
}

.score-name {
  font-size: 12px;
  color: #64748b;
}

.score-val {
  font-size: 22px;
  font-weight: 700;
  margin: 4px 0;
}

.score-dir {
  font-size: 12px;
  color: #64748b;
}

.risk-block {
  margin-top: 8px;
  padding: 12px;
  border-radius: 10px;
  background: var(--risk-bg, #fff7ed);
  border: 1px solid var(--risk-border, #fed7aa);
}

.risk-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--risk-title, #c2410c);
  margin-bottom: 4px;
}

.risk-text {
  font-size: 13px;
  color: var(--risk-text, #9a3412);
  line-height: 1.6;
}
</style>
