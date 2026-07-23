<template>
  <div class="app-container quant-longbridge">
    <el-card shadow="never" class="config-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">长桥 Longbridge 接入配置</span>
          <el-tag v-if="statusChecked" :type="configured ? 'success' : 'info'" effect="dark">
            {{ configured ? '已连接' : '未连接' }}
          </el-tag>
        </div>
      </template>

      <el-alert
        title="填写长桥开放平台凭据以启用实时行情与交易能力。凭据将加密保存，请妥善保管。"
        type="info"
        :closable="false"
        show-icon
        class="mb16"
      />

      <el-form ref="cfgRef" :model="form" :rules="rules" label-width="130px" style="max-width: 640px">
        <el-form-item label="App Key" prop="appKey">
          <el-input v-model="form.appKey" placeholder="请输入 App Key" autocomplete="off" />
        </el-form-item>
        <el-form-item label="App Secret" prop="appSecret">
          <el-input
            v-model="form.appSecret"
            :type="showSecret ? 'text' : 'password'"
            placeholder="请输入 App Secret"
            autocomplete="new-password"
          >
            <template #suffix>
              <el-icon class="eye-toggle" @click="showSecret = !showSecret">
                <View v-if="showSecret" /><Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="Access Token" prop="accessToken">
          <el-input
            v-model="form.accessToken"
            :type="showToken ? 'text' : 'password'"
            placeholder="请输入 Access Token"
            autocomplete="new-password"
          >
            <template #suffix>
              <el-icon class="eye-toggle" @click="showToken = !showToken">
                <View v-if="showToken" /><Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="地区" prop="region">
          <el-select v-model="form.region" placeholder="选择地区" style="width: 220px">
            <el-option label="中国大陆 (cn)" value="cn" />
            <el-option label="香港 (hk)" value="hk" />
            <el-option label="海外 (overseas)" value="overseas" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saveLoading" @click="submitForm" v-hasPermi="['quant:longbridge:config']">保 存</el-button>
          <el-button type="success" plain :loading="testLoading" @click="handleTest" v-hasPermi="['quant:longbridge:test']">测试连接</el-button>
          <el-button @click="getConfigData">重 置</el-button>
        </el-form-item>
      </el-form>

      <div class="test-result" v-if="testResult">
        <div class="result-title">
          <el-icon :color="testResult.configured ? '#67c23a' : '#f56c6c'">
            <CircleCheck v-if="testResult.configured" /><CircleClose v-else />
          </el-icon>
          <span>{{ testResult.configured ? '连接成功' : '连接失败' }}</span>
        </div>
        <div class="result-msg">{{ testResult.message || '--' }}</div>
      </div>
    </el-card>
  </div>
</template>

<script setup name="QuantLongbridge">
import { getLongbridgeConfig, updateLongbridgeConfig, testLongbridge } from '@/api/quant';

const { proxy } = getCurrentInstance();

const loading = ref(false);
const saveLoading = ref(false);
const testLoading = ref(false);
const showSecret = ref(false);
const showToken = ref(false);
const testResult = ref(null);
const statusChecked = ref(false);
const configured = ref(false);

const form = ref({
  appKey: '',
  appSecret: '',
  accessToken: '',
  region: 'cn'
});

const rules = {
  appKey: [{ required: true, message: 'App Key 不能为空', trigger: 'blur' }],
  appSecret: [{ required: true, message: 'App Secret 不能为空', trigger: 'blur' }],
  accessToken: [{ required: true, message: 'Access Token 不能为空', trigger: 'blur' }]
};

/** 查询配置 */
function getConfigData() {
  loading.value = true;
  getLongbridgeConfig().then(response => {
    const data = response.data || {};
    form.value = {
      appKey: data.appKey || '',
      appSecret: data.appSecret || '',
      accessToken: data.accessToken || '',
      region: data.region || 'cn'
    };
    configured.value = !!(data.appKey && data.accessToken);
    statusChecked.value = true;
    loading.value = false;
  }).catch(() => {
    loading.value = false;
  });
}

/** 保存配置 */
function submitForm() {
  proxy.$refs['cfgRef'].validate(valid => {
    if (valid) {
      saveLoading.value = true;
      updateLongbridgeConfig(form.value).then(() => {
        proxy.$modal.msgSuccess('保存成功');
        getConfigData();
      }).finally(() => {
        saveLoading.value = false;
      });
    }
  });
}

/** 测试连接 */
function handleTest() {
  testLoading.value = true;
  testResult.value = null;
  testLongbridge().then(response => {
    testResult.value = response.data || {};
    configured.value = !!testResult.value.configured;
    statusChecked.value = true;
    if (testResult.value.configured) {
      proxy.$modal.msgSuccess('连接成功');
    } else {
      proxy.$modal.msgWarning(testResult.value.message || '连接失败');
    }
  }).finally(() => {
    testLoading.value = false;
  });
}

getConfigData();
</script>

<style lang="scss" scoped>
.quant-longbridge {
  .mb16 { margin-bottom: 16px; }
  .config-card {
    border-radius: 14px;
    max-width: 900px;
    .card-header {
      display: flex; align-items: center; justify-content: space-between;
      .card-title { font-size: 15px; font-weight: 600; color: var(--text-emphasis, #303133); }
    }
  }
  .eye-toggle {
    cursor: pointer;
    color: #909399;
    &:hover { color: #409eff; }
  }
  .test-result {
    margin-top: 16px;
    padding: 14px 18px;
    border-radius: 10px;
    background: var(--surface-muted, #f5f7fa);
    max-width: 640px;
    .result-title {
      display: flex; align-items: center; gap: 8px;
      font-size: 14px; font-weight: 600; color: var(--text-emphasis, #303133);
    }
    .result-msg {
      margin-top: 6px; font-size: 13px; color: #606266; line-height: 1.6;
    }
  }
}
</style>
