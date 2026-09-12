<template>
  <div class="app-container">
    <el-card shadow="never" class="config-card mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">模型连接（只读）</span>
          <el-button type="primary" link @click="goAiModel">去 AI 管理配置模型</el-button>
        </div>
      </template>
      <el-alert
        v-if="!form.modelName"
        type="warning"
        show-icon
        :closable="false"
        title="未检测到可用 AI 模型。请先在「AI 管理 → 模型管理」新增并启用模型（填写 Base URL / API Key / 模型编码）。"
        class="mb12"
      />
      <el-descriptions v-else :column="1" border size="small">
        <el-descriptions-item label="当前模型">{{ form.modelName }}</el-descriptions-item>
        <el-descriptions-item label="适用范围">{{ form.modelScope || '自动解析' }}</el-descriptions-item>
        <el-descriptions-item label="API 地址">{{ form.baseUrl || '--' }}</el-descriptions-item>
        <el-descriptions-item label="温度">{{ form.temperature ?? '--' }}</el-descriptions-item>
      </el-descriptions>
      <div class="hint">舆情优先 sentiment → Grok 4.6 → global → chat。智能选股 / 自选分析优先「行情中心 (market)」，默认 Grok 4.6。</div>
    </el-card>

    <el-card shadow="never" class="config-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">舆情业务配置</span>
        </div>
      </template>
      <el-form ref="configRef" :model="form" label-width="140px" style="max-width: 720px">
        <el-form-item label="单轮分析资讯数" prop="maxNewsPerRound">
          <el-input-number v-model="form.maxNewsPerRound" :min="1" :max="200" />
          <div class="field-hint">每次分析仅处理最近约 10 分钟内未分析的资讯，上限 200 条（安全封顶）。</div>
        </el-form-item>
        <el-form-item label="自动分析" prop="autoAnalyze">
          <el-switch v-model="form.autoAnalyze" active-value="1" inactive-value="0" active-text="开" inactive-text="关" />
        </el-form-item>
        <el-form-item label="启用来源" prop="enabledSources">
          <el-checkbox-group v-model="enabledSourceList">
            <el-checkbox value="eastmoney">东方财富</el-checkbox>
            <el-checkbox value="sina">新浪财经</el-checkbox>
            <el-checkbox value="ths">同花顺</el-checkbox>
            <el-checkbox value="wallstreetcn">华尔街见闻</el-checkbox>
            <el-checkbox value="google_news">谷歌新闻(中文)</el-checkbox>
            <el-checkbox value="jin10">金十数据</el-checkbox>
            <el-checkbox value="x_monitor">X</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saveLoading" @click="submitForm" v-hasPermi="['sentiment:config:edit']">保 存</el-button>
          <el-button @click="getConfigData">重 置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup name="SentimentConfig">
import { getConfig, updateConfig } from '@/api/sentiment'

const { proxy } = getCurrentInstance()
const router = useRouter()

const loading = ref(true)
const saveLoading = ref(false)
const enabledSourceList = ref([])

const form = ref({
  configId: undefined,
  baseUrl: undefined,
  apiKey: undefined,
  modelName: undefined,
  temperature: 0.7,
  maxNewsPerRound: 200,
  autoAnalyze: '0',
  enabledSources: '',
  modelScope: undefined,
  modelId: undefined
})

function goAiModel() {
  router.push('/ai/model')
}

function getConfigData() {
  loading.value = true
  getConfig()
    .then(response => {
      const data = response.data || {}
      form.value = {
        configId: data.configId,
        baseUrl: data.baseUrl,
        apiKey: data.apiKey,
        modelName: data.modelName,
        temperature: data.temperature != null ? Number(data.temperature) : 0.7,
        maxNewsPerRound: data.maxNewsPerRound != null ? Number(data.maxNewsPerRound) : 200,
        autoAnalyze: data.autoAnalyze != null ? String(data.autoAnalyze) : '0',
        enabledSources: data.enabledSources || '',
        modelScope: data.modelScope,
        modelId: data.modelId
      }
      enabledSourceList.value = form.value.enabledSources
        ? form.value.enabledSources.split(',').map(s => s.trim()).filter(Boolean)
        : ['eastmoney', 'sina', 'ths', 'wallstreetcn', 'google_news', 'x_monitor']
    })
    .finally(() => {
      loading.value = false
    })
}

function submitForm() {
  saveLoading.value = true
  const data = {
    configId: form.value.configId,
    maxNewsPerRound: form.value.maxNewsPerRound,
    autoAnalyze: form.value.autoAnalyze,
    enabledSources: enabledSourceList.value.join(',')
  }
  updateConfig(data)
    .then(() => {
      proxy.$modal.msgSuccess('保存成功')
      getConfigData()
    })
    .finally(() => {
      saveLoading.value = false
    })
}

getConfigData()
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  font-weight: 600;
}
.mb16 {
  margin-bottom: 16px;
}
.mb12 {
  margin-bottom: 12px;
}
.hint {
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}
.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
