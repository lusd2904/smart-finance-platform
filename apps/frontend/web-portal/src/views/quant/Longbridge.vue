<template>
  <PageFrame
    title="长桥配置"
    subtitle="凭据脱敏 · 账户绑定 · 自动交易默认关闭 · 对齐 /quant/longbridge"
    badge="「长桥配置 /quant/longbridge」"
    :loading="loading"
  >
    <template #actions>
      <el-tag :type="connected ? 'success' : 'info'" effect="plain">{{ connected ? '已连接' : '未连接' }}</el-tag>
      <el-button type="success" :loading="testing" @click="test">测试连接</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>

    <el-card shadow="never" class="glass-panel">
      <el-form :model="form" label-width="120px" style="max-width:560px">
        <el-form-item label="App Key">
          <el-input v-model="form.appKey" type="password" show-password autocomplete="off" placeholder="**** 脱敏回显" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input v-model="form.appSecret" type="password" show-password autocomplete="new-password" placeholder="**** 不覆盖原值" />
        </el-form-item>
        <el-form-item label="Access Token">
          <el-input v-model="form.accessToken" type="password" show-password autocomplete="new-password" placeholder="**** 不覆盖原值" />
        </el-form-item>
        <el-form-item label="账户绑定">
          <el-select v-model="form.region" style="width:220px">
            <el-option label="中国大陆 (cn)" value="cn" />
            <el-option label="香港 (hk)" value="hk" />
            <el-option label="海外 (overseas)" value="overseas" />
          </el-select>
        </el-form-item>
        <el-form-item label="自动交易">
          <el-switch v-model="form.autoTradeEnabled" />
          <span class="muted">默认关闭 · 未配置 Key 时保持 OFF</span>
        </el-form-item>
      </el-form>
      <p v-if="testMsg" class="test-msg">{{ testMsg }}</p>
    </el-card>

    <template #legend>
      <span>GET/PUT /quant/longbridge/config · Secret/Token 以 **** 开头不覆盖 · 永不展示明文</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { getLongbridgeConfig, testLongbridge, updateLongbridgeConfig } from '@/api/quant'
import { unwrap } from '@/utils/list'
import { isMaskedSecret, maskSecret, sanitizePublicText } from '@/utils/secret'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const connected = ref(false)
const testMsg = ref('')
const form = reactive({
  appKey: '',
  appSecret: '',
  accessToken: '',
  region: 'cn',
  autoTradeEnabled: false
})

async function load() {
  loading.value = true
  try {
    const data = unwrap(await getLongbridgeConfig())
    const key = data.appKey || data.app_key || ''
    const secret = data.appSecret || data.app_secret || ''
    const token = data.accessToken || data.access_token || ''
    form.appKey = maskSecret(key)
    form.appSecret = secret ? maskSecret(secret) : ''
    form.accessToken = token ? maskSecret(token) : ''
    form.region = data.region || 'cn'
    form.autoTradeEnabled = Boolean(data.autoTradeEnabled)
    connected.value = Boolean(key)
  } catch {
    form.autoTradeEnabled = false
  } finally {
    loading.value = false
  }
}

function payload() {
  const data = {
    region: form.region,
    autoTradeEnabled: form.autoTradeEnabled
  }
  if (!isMaskedSecret(form.appKey)) data.appKey = form.appKey
  if (!isMaskedSecret(form.appSecret)) data.appSecret = form.appSecret
  if (!isMaskedSecret(form.accessToken)) data.accessToken = form.accessToken
  return data
}

async function save() {
  saving.value = true
  try {
    await updateLongbridgeConfig(payload())
    ElMessage.success('已保存')
    load()
  } catch (e) {
    ElMessage.error(sanitizePublicText(e?.message, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  try {
    const data = unwrap(await testLongbridge())
    connected.value = Boolean(data.connected || data.configured)
    testMsg.value = sanitizePublicText(data.message, connected.value ? '连接正常' : '未连接')
    ElMessage[connected.value ? 'success' : 'warning'](testMsg.value)
  } catch (e) {
    connected.value = false
    testMsg.value = sanitizePublicText(e?.message, '连接失败')
    ElMessage.error(testMsg.value)
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.muted { margin-left: 10px; color: var(--text-secondary); font-size: 12px; }
.test-msg { color: var(--text-secondary); font-size: 13px; }
</style>
