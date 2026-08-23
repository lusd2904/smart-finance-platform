<template>
  <div class="app-container" style="max-width: 720px">
    <el-alert
      title="仅飞书。个人与群分开订阅，两边都开才双发。非交易日、空清单、停牌日默认不推。卡片版式固定并含免责声明。"
      type="info"
      show-icon
      :closable="false"
      class="mb16"
    />
    <el-form :model="form" label-width="140px" v-loading="loading">
      <el-form-item label="个人会话">
        <el-switch v-model="form.personalEnabled" />
      </el-form-item>
      <el-form-item label="个人 Webhook">
        <el-input v-model="form.personalWebhook" placeholder="飞书自定义机器人 Webhook" />
      </el-form-item>
      <el-form-item label="群">
        <el-switch v-model="form.groupEnabled" />
      </el-form-item>
      <el-form-item label="群 Webhook">
        <el-input v-model="form.groupWebhook" placeholder="把机器人拉进群后填写群 Webhook" />
      </el-form-item>
      <el-form-item label="推送时间">
        <el-time-select
          v-model="form.pushTime"
          start="08:00"
          step="00:15"
          end="22:00"
          placeholder="用户本地时间"
        />
      </el-form-item>
      <el-form-item label="时区">
        <el-input v-model="form.timezone" placeholder="Asia/Shanghai" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSave" v-hasPermi="['trade:feishu:edit']">保存</el-button>
        <el-button @click="handleTest('personal')" v-hasPermi="['trade:feishu:test']">测试个人</el-button>
        <el-button @click="handleTest('group')" v-hasPermi="['trade:feishu:test']">测试群</el-button>
      </el-form-item>
    </el-form>
    <p class="muted">口径为策略摘要而非荐股。模板不可改版式。</p>
  </div>
</template>

<script setup name="TradeFeishuPushIndex">
import { getFeishuConfig, saveFeishuConfig, testFeishuPush } from '@/api/trade'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const saving = ref(false)
const form = ref({
  personalEnabled: false,
  groupEnabled: false,
  personalWebhook: '',
  groupWebhook: '',
  pushTime: '18:30',
  timezone: 'Asia/Shanghai'
})

async function load() {
  loading.value = true
  try {
    const res = await getFeishuConfig()
    form.value = Object.assign(form.value, res.data || {})
  } finally {
    loading.value = false
  }
}

function handleSave() {
  saving.value = true
  saveFeishuConfig(form.value)
    .then(() => proxy.$modal.msgSuccess('已保存'))
    .finally(() => { saving.value = false })
}

function handleTest(channel) {
  testFeishuPush({ channel }).then(res => {
    proxy.$modal.msgSuccess(res.msg || '已发送测试卡片')
  })
}

onMounted(load)
</script>

<style scoped>
.mb16 { margin-bottom: 16px; }
.muted { color: #909399; font-size: 13px; }
</style>
