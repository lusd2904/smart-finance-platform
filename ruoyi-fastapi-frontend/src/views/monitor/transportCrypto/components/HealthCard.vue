<template>
  <el-card shadow="never" class="health-card">
    <template #header>
      <div class="card-header">
        <span>运行健康度</span>
        <el-tag :type="healthTagLabelType">{{ healthLabel }}</el-tag>
      </div>
    </template>

    <div class="health-item">
      <div class="health-label">
        <span>解密成功率</span>
        <span>{{ decryptSuccessRate.toFixed(1) }}%</span>
      </div>
      <el-progress :percentage="Number(decryptSuccessRate.toFixed(1))" :status="healthProgressStatus" />
    </div>

    <div class="health-item">
      <div class="health-label">
        <span>加密请求占比</span>
        <span>{{ encryptedRequestRate.toFixed(1) }}%</span>
      </div>
      <el-progress :percentage="Number(encryptedRequestRate.toFixed(1))" status="success" />
    </div>

    <div class="health-item">
      <div class="health-label">
        <span>加密响应占比</span>
        <span>{{ encryptedResponseRate.toFixed(1) }}%</span>
      </div>
      <el-progress :percentage="Number(encryptedResponseRate.toFixed(1))" />
    </div>

    <el-alert
      :title="healthMessage"
      :type="healthTagType"
      :closable="false"
      show-icon
    />
  </el-card>
</template>

<script setup name="TransportCryptoHealthCard">
import { computed } from 'vue'
import { getRate } from '../utils'

const props = defineProps({
  monitorData: { type: Object, required: true }
})

const decryptSuccessRate = computed(() =>
  getRate(
    props.monitorData.decryptSuccessTotal,
    props.monitorData.decryptSuccessTotal + props.monitorData.decryptFailureTotal
  )
)

const encryptedRequestRate = computed(() =>
  getRate(props.monitorData.encryptedRequestsTotal, props.monitorData.requestsTotal)
)

const encryptedResponseRate = computed(() =>
  getRate(
    props.monitorData.encryptedResponsesTotal,
    props.monitorData.encryptedResponsesTotal + props.monitorData.plainResponsesTotal
  )
)

const healthLabel = computed(() => {
  if ((props.monitorData.decryptFailureTotal || 0) === 0) {
    return '稳定'
  }
  if (decryptSuccessRate.value >= 95) {
    return '良好'
  }
  if (decryptSuccessRate.value >= 80) {
    return '关注'
  }
  return '告警'
})

const healthTagType = computed(() => {
  if ((props.monitorData.decryptFailureTotal || 0) === 0) {
    return 'success'
  }
  if (decryptSuccessRate.value >= 95) {
    return 'success'
  }
  if (decryptSuccessRate.value >= 80) {
    return 'warning'
  }
  return 'error'
})

const healthTagLabelType = computed(() => healthTagType.value === 'error' ? 'danger' : healthTagType.value)

const healthProgressStatus = computed(() => {
  if (decryptSuccessRate.value >= 95) {
    return 'success'
  }
  if (decryptSuccessRate.value >= 80) {
    return 'warning'
  }
  return 'exception'
})

const healthMessage = computed(() => {
  if ((props.monitorData.decryptFailureTotal || 0) === 0) {
    return '当前暂无解密失败记录，链路运行稳定。'
  }
  if (decryptSuccessRate.value >= 95) {
    return '存在少量失败事件，建议继续观察失败原因分布。'
  }
  if (decryptSuccessRate.value >= 80) {
    return '近期已有一定比例的异常请求，建议优先检查失败原因与最近失败记录。'
  }
  return '异常比例偏高，建议立即排查密钥版本、AAD 绑定、时间窗与重放校验。'
})
</script>

<style lang="scss" scoped>
@import './card-common.scss';
@import './health-card.scss';
</style>
