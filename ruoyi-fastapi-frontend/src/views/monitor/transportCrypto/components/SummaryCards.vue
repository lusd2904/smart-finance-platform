<template>
  <el-row :gutter="16" class="mb16">
    <el-col :xs="24" :sm="12" :lg="6">
      <el-card shadow="hover" class="summary-card">
        <div class="summary-header">
          <span class="summary-title">传输加密状态</span>
          <el-tag :type="monitorData.transportCryptoEnabled ? 'success' : 'info'">
            {{ monitorData.transportCryptoEnabled ? '已启用' : '未启用' }}
          </el-tag>
        </div>
        <div class="summary-value">{{ modeLabel }}</div>
        <div class="summary-desc">
          当前模式：{{ monitorData.transportCryptoMode || '-' }}
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :sm="12" :lg="6">
      <el-card shadow="hover" class="summary-card">
        <div class="summary-header">
          <span class="summary-title">请求总览</span>
          <el-tag type="primary">命中规则</el-tag>
        </div>
        <div class="summary-value">{{ formatCount(monitorData.requestsTotal) }}</div>
        <div class="summary-desc">
          明文 {{ formatCount(monitorData.plainRequestsTotal) }} / 加密 {{ formatCount(monitorData.encryptedRequestsTotal) }}
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :sm="12" :lg="6">
      <el-card shadow="hover" class="summary-card">
        <div class="summary-header">
          <span class="summary-title">解密成功率</span>
          <el-tag :type="decryptSuccessRate >= 95 ? 'success' : decryptSuccessRate >= 80 ? 'warning' : 'danger'">
            {{ decryptSuccessRate.toFixed(1) }}%
          </el-tag>
        </div>
        <div class="summary-value">{{ formatCount(monitorData.decryptSuccessTotal) }}</div>
        <div class="summary-desc">
          失败 {{ formatCount(monitorData.decryptFailureTotal) }} / 强制拒绝 {{ formatCount(monitorData.requiredRejectedTotal) }}
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :sm="12" :lg="6">
      <el-card shadow="hover" class="summary-card">
        <div class="summary-header">
          <span class="summary-title">响应加密</span>
          <el-tag type="warning">JSON 响应</el-tag>
        </div>
        <div class="summary-value">{{ formatCount(monitorData.encryptedResponsesTotal) }}</div>
        <div class="summary-desc">
          明文 {{ formatCount(monitorData.plainResponsesTotal) }} / 错误加密 {{ formatCount(monitorData.encryptedErrorResponsesTotal) }}
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup name="TransportCryptoSummaryCards">
import { computed } from 'vue'
import { MODE_LABEL_MAP, formatCount, getRate } from '../utils'

const props = defineProps({
  monitorData: { type: Object, required: true }
})

const modeLabel = computed(() => MODE_LABEL_MAP[props.monitorData.transportCryptoMode] || '未配置')

const decryptSuccessRate = computed(() =>
  getRate(
    props.monitorData.decryptSuccessTotal,
    props.monitorData.decryptSuccessTotal + props.monitorData.decryptFailureTotal
  )
)
</script>

<style lang="scss" scoped>
@import './summary-cards.scss';
</style>
