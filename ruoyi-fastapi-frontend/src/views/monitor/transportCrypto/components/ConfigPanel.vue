<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span>当前配置</span>
        <div class="card-actions">
          <el-switch
            :model-value="autoRefresh"
            inline-prompt
            active-text="自动刷新"
            inactive-text="手动"
            @update:model-value="$emit('update:autoRefresh', $event)"
          />
          <el-button type="primary" icon="Refresh" :loading="loading" @click="$emit('refresh')">
            刷新
          </el-button>
        </div>
      </div>
    </template>

    <el-descriptions :column="2" border>
      <el-descriptions-item label="统计范围">
        {{ monitorScopeLabel }}
      </el-descriptions-item>
      <el-descriptions-item label="应用环境">
        {{ monitorData.appEnv || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="当前密钥版本">
        <el-tag>{{ monitorData.currentKid || '-' }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="监控起始时间">
        {{ formatMonitorTime(monitorData.startedAt) || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="支持的密钥版本">
        <div class="tag-list">
          <el-tag v-for="kid in monitorData.supportedKids || []" :key="kid" class="tag-item" effect="plain">
            {{ kid }}
          </el-tag>
          <span v-if="!(monitorData.supportedKids || []).length">-</span>
        </div>
      </el-descriptions-item>
      <el-descriptions-item label="失败原因种类">
        {{ failureReasonRows.length }}
      </el-descriptions-item>
      <el-descriptions-item label="聚合说明" :span="2">
        {{ monitorScopeDescription }}
      </el-descriptions-item>
      <el-descriptions-item label="启用路径">
        <div class="tag-list">
          <el-tag
            v-for="path in monitorData.enabledPaths || []"
            :key="path"
            type="success"
            class="tag-item"
            effect="plain"
          >
            {{ path }}
          </el-tag>
          <span v-if="!(monitorData.enabledPaths || []).length">全部接口</span>
        </div>
      </el-descriptions-item>
      <el-descriptions-item label="强制加密路径">
        <div class="tag-list">
          <el-tag
            v-for="path in monitorData.requiredPaths || []"
            :key="path"
            type="warning"
            class="tag-item"
            effect="plain"
          >
            {{ path }}
          </el-tag>
          <span v-if="!(monitorData.requiredPaths || []).length">-</span>
        </div>
      </el-descriptions-item>
      <el-descriptions-item label="排除路径" :span="2">
        <div class="tag-list">
          <el-tag
            v-for="path in monitorData.excludePaths || []"
            :key="path"
            type="info"
            class="tag-item"
            effect="plain"
          >
            {{ path }}
          </el-tag>
          <span v-if="!(monitorData.excludePaths || []).length">-</span>
        </div>
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<script setup name="TransportCryptoConfigPanel">
import { computed } from 'vue'
import { MONITOR_SCOPE_LABEL_MAP, formatMonitorTime } from '../utils'

const props = defineProps({
  monitorData: { type: Object, required: true },
  autoRefresh: { type: Boolean, default: true },
  loading: { type: Boolean, default: false }
})

defineEmits(['update:autoRefresh', 'refresh'])

const failureReasonRows = computed(() => {
  const failureReasons = props.monitorData.failureReasons || {}
  return Object.keys(failureReasons)
})

const monitorScopeLabel = computed(
  () => MONITOR_SCOPE_LABEL_MAP[props.monitorData.monitorScope] || props.monitorData.monitorScope || '-'
)

const monitorScopeDescription = computed(() => {
  if (props.monitorData.monitorScope === 'redis-aggregated') {
    return '统计结果已聚合到 Redis，可覆盖多 worker / 多实例共享的监控口径。'
  }
  if (props.monitorData.monitorScope === 'redis-aggregated+local-fallback') {
    return '当前以 Redis 聚合为主，部分监控写入曾降级到本地内存，建议检查 Redis 连接稳定性。'
  }
  if (props.monitorData.monitorScope === 'process-local-fallback') {
    return '当前监控未写入 Redis，页面展示的是本进程本地统计，请优先检查 Redis 可用性。'
  }
  return '当前展示传输加密运行状态与统计信息。'
})
</script>

<style lang="scss" scoped>
@import './card-common.scss';
</style>
