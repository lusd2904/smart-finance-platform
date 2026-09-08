<template>
  <PageFrame title="长桥配置" subtitle="行情 / 交易通道" badge="「长桥配置 /quant/longbridge」" :loading="loading">
    <template #actions>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      <el-button :loading="testing" @click="test">测试连接</el-button>
    </template>
    <el-card shadow="never" class="glass-panel">
      <el-form :model="form" label-width="100px" style="max-width:480px">
        <el-form-item label="App Key">
          <el-input v-model="form.appKey" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input v-model="form.appSecret" type="password" show-password />
        </el-form-item>
        <el-form-item label="Access Token">
          <el-input v-model="form.accessToken" type="password" show-password />
        </el-form-item>
        <el-form-item label="环境">
          <el-select v-model="form.env" style="width:160px">
            <el-option label="正式" value="prod" />
            <el-option label="模拟" value="paper" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>
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
const form = reactive({ appKey: '', appSecret: '', accessToken: '', env: 'paper' })

async function load() {
  loading.value = true
  try {
    const data = unwrap(await getLongbridgeConfig())
    Object.assign(form, {
      appKey: data.appKey || data.app_key || '',
      appSecret: data.appSecret || '',
      accessToken: data.accessToken || '',
      env: data.env || data.environment || 'paper'
    })
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await updateLongbridgeConfig({ ...form })
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  try {
    await testLongbridge()
    ElMessage.success('连接正常')
  } catch (e) {
    ElMessage.error(e?.message || '连接失败')
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>
