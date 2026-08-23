<template>
  <el-dialog v-model="visible" title="用户全局配置" width="700px" append-to-body class="chat-config-dialog">
    <el-form :model="editing" label-width="150px">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="默认温度">
            <el-input-number
              v-model="editing.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              :precision="1"
              placeholder="默认温度"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="附带历史消息">
            <el-switch active-value="0" inactive-value="1" v-model="editing.addHistoryToContext" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="历史消息轮数" v-if="editing.addHistoryToContext == '0'">
            <el-input-number
              v-model="editing.numHistoryRuns"
              :min="1"
              :max="20"
              placeholder="历史消息轮数"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="默认显示指标">
            <el-switch active-value="0" inactive-value="1" v-model="editing.metricsDefaultVisible" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="开启视觉功能">
            <el-switch active-value="0" inactive-value="1" v-model="editing.visionEnabled" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="图片最大大小" v-if="editing.visionEnabled">
            <el-input-number
              v-model="editing.imageMaxSizeMb"
              :min="1"
              :max="50"
              placeholder="图片大小"
              style="width: 100%"
            >
              <template #suffix>
                <span>MB</span>
              </template>
            </el-input-number>
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="系统提示词">
            <el-input v-model="editing.systemPrompt" type="textarea" :rows="4" placeholder="设置全局系统提示词" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="emit('save', { ...editing })">保存</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup name="AiChatUserConfigDialog">
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  config: { type: Object, required: true }
})

const emit = defineEmits(['update:modelValue', 'save'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 打开时从父级拷贝一份作为编辑副本，保存时整体上抛，避免直接修改父级状态
const editing = reactive({ ...props.config })

watch(visible, (val) => {
  if (val) Object.assign(editing, props.config)
})
</script>

<style scoped lang="scss">
.chat-config-dialog {
  :deep(.el-dialog__body) {
    padding-top: 10px;
    padding-bottom: 10px;
  }

  :deep(.el-form-item) {
    margin-bottom: 16px;
  }

  :deep(.el-form-item__label) {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }
}
</style>
