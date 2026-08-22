<template>
  <el-card shadow="never" class="panel-card">
    <template #header>
      <div class="panel-header">
        <span class="panel-title">财经简报</span>
        <el-button link type="primary" @click="go('/market/finance-news')">更多</el-button>
      </div>
    </template>

    <template v-if="items.length">
      <div class="brief-row" v-for="(b, idx) in items" :key="idx">
        <div class="brief-main">
          <el-tag size="small" effect="plain" class="brief-market">{{ marketLabel(b.market) }}</el-tag>
          <span class="brief-headline" :title="b.summary">{{ b.headline }}</span>
        </div>
        <div class="brief-meta">
          <span v-if="b.sourceName" class="brief-source">{{ b.sourceName }}</span>
          <a
            v-if="b.sourceLink"
            :href="b.sourceLink"
            target="_blank"
            rel="noopener noreferrer"
            class="brief-link"
            @click.stop
          >原文</a>
          <span class="brief-time">{{ b.generatedAt }}</span>
        </div>
      </div>
    </template>
    <el-empty v-else :description="reason" :image-size="80" />
  </el-card>
</template>

<script setup name="DashBriefingStream">
import { sectionOk, sectionReason } from '../utils'

const props = defineProps({
  section: { type: Object, default: null }
})

const router = useRouter()
const denied = computed(() => props.section && props.section.reason === 'denied')
const hasData = computed(() => sectionOk(props.section))
const items = computed(() => (hasData.value ? props.section.data : []) || [])
const reason = computed(() =>
  denied.value ? '无简报查看权限' : sectionReason(props.section, '简报尚未生成，采集任务完成后展示')
)

function marketLabel(market) {
  return { US: '美股', HK: '港股', CN: 'A股' }[market] || market || '综合'
}

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

.brief-row {
  padding: 8px 4px;
  border-bottom: 1px dashed var(--border-soft, #eef2ff);

  &:last-child {
    border-bottom: none;
  }
}

.brief-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brief-market {
  flex-shrink: 0;
}

.brief-headline {
  font-size: 13px;
  color: var(--text-emphasis, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brief-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 3px;
  padding-left: 46px;
  font-size: 12px;
  color: #94a3b8;
}

.brief-link {
  color: var(--el-color-primary);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}
</style>
