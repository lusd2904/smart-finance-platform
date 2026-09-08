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
          <el-input v-model="form.appKey" autocomplete="off" placeholder="**** 脱敏回显" />
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

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const connected = ref(false)
const testMsg = ref('')
const rawKey = ref('')
const form = reactive({
  appKey: '',
  appSecret: '',
  accessToken: '',
  region: 'cn',
  autoTradeEnabled: false
})

function mask(value) {
  const text = String(value || '')
  if (!text) return ''
  if (text.startsWith('****')) return text
  return text.length > 4 ? `****${text.slice(-4)}` : '****'
}
function isMasked(value) {
  return Boolean(value) && String(value).startsWith('****')
}

async function load() {
  loading.value = true
  try {
    const data = unwrap(await getLongbridgeConfig())
    rawKey.value = data.appKey || data.app_key || ''
    form.appKey = mask(rawKey.value)
    form.appSecret = data.appSecret || data.app_secret || ''
    form.accessToken = data.accessToken || data.access_token || ''
    form.region = data.region || 'cn'
    form.autoTradeEnabled = Boolean(data.autoTradeEnabled)
    connected.value = Boolean(rawKey.value)
  } catch {
    form.autoTradeEnabled = false
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await updateLongbridgeConfig({
      appKey: isMasked(form.appKey) ? rawKey.value : form.appKey,
      appSecret: form.appSecret,
      accessToken: form.accessToken,
      region: form.region,
      autoTradeEnabled: form.autoTradeEnabled
    })
    ElMessage.success('已保存')
    load()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  try {
    const data = unwrap(await testLongbridge())
    connected.value = Boolean(data.connected || data.configured)
    testMsg.value = data.message || (connected.value ? '连接正常' : '未连接')
    ElMessage[connected.value ? 'success' : 'warning'](testMsg.value)
  } catch (e) {
    connected.value = false
    testMsg.value = e?.message || '连接失败'
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
