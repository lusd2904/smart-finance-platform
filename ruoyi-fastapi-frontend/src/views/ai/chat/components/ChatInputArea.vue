<template>
  <div class="chat-input-area">
    <div class="input-wrapper">
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        resize="none"
        placeholder="请输入您的问题... (Enter 发送，Shift + Enter 换行)"
        @keydown.enter.exact.prevent="emit('send')"
        :disabled="loading"
      />
      <div class="selected-images" v-if="visionEnabled == '0' && inputImages.length">
        <el-image
          v-for="(img, idx) in inputImages"
          :key="idx"
          :src="getImageUrl(img)"
          :preview-src-list="inputImages.map(getImageUrl)"
          fit="cover"
          class="selected-image-item"
        />
      </div>
      <div class="input-actions">
        <div class="left-actions">
          <el-tooltip
            v-if="modelInfo && modelInfo.supportImages === 'Y' && visionEnabled == '0'"
            content="上传图片"
            placement="top"
          >
            <el-button circle text :icon="Picture" @click="triggerImageUpload" />
          </el-tooltip>
          <el-button
            v-if="modelInfo && modelInfo.supportReasoning === 'Y'"
            class="toggle-chip"
            size="small"
            :type="isReasoning ? 'primary' : ''"
            :plain="!isReasoning"
            @click="isReasoning = !isReasoning"
          >
            <template #icon>
              <svg-icon icon-class="deepthink" />
            </template>
            深度思考
          </el-button>
        </div>
        <el-button
          :type="loading ? 'danger' : 'primary'"
          :icon="loading ? 'VideoPause' : 'Promotion'"
          @click="emit('main-action')"
          :disabled="!loading && !inputMessage.trim() && !inputImages.length"
        >
          {{ loading ? '停止' : '发送' }}
        </el-button>
      </div>
    </div>
    <input
      ref="imageInputRef"
      type="file"
      accept="image/*"
      multiple
      class="chat-image-input"
      @change="handleImageInputChange"
    />
  </div>
</template>

<script setup name="AiChatInputArea">
import { Picture } from '@element-plus/icons-vue'
import { getToken } from '@/utils/auth'
import { getImageUrl } from '../utils'

const props = defineProps({
  loading: { type: Boolean, default: false },
  visionEnabled: { type: String, default: '1' },
  imageMaxSizeMb: { type: Number, default: 5 },
  modelInfo: { type: Object, default: null }
})

// 双向绑定字段：父组件用 v-model:input-message / v-model:input-images / v-model:is-reasoning
const inputMessage = defineModel('inputMessage', { type: String, default: '' })
const inputImages = defineModel('inputImages', { type: Array, default: () => [] })
const isReasoning = defineModel('isReasoning', { type: Boolean, default: true })

const emit = defineEmits(['send', 'main-action'])

const { proxy } = getCurrentInstance()
const imageInputRef = ref(null)

function triggerImageUpload() {
  if (!props.visionEnabled || props.loading) return
  const input = imageInputRef.value
  if (input) {
    input.value = ''
    input.click()
  }
}

async function handleImageInputChange(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  if (files.length + props.inputImages.length > 10) {
    proxy.$modal.msgError('最多只能上传 10 张图片')
    return
  }
  const maxSize = (props.imageMaxSizeMb || 5) * 1024 * 1024
  for (const file of files) {
    if (file.size > maxSize) {
      proxy.$modal.msgError(`单张图片大小不能超过 ${props.imageMaxSizeMb} MB`)
      return
    }
  }
  try {
    proxy.$modal.loading('正在上传图片，请稍候...')
    const uploaded = []
    for (const file of files) {
      const form = new FormData()
      form.append('file', file)
      const resp = await fetch(import.meta.env.VITE_APP_BASE_API + '/common/upload', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer ' + getToken()
        },
        body: form
      })
      const data = await resp.json()
      if (data.code === 200 && data.fileName) {
        uploaded.push(data.fileName)
      } else {
        proxy.$modal.msgError(data.msg || '上传图片失败')
      }
    }
    if (uploaded.length) {
      inputImages.value = [...inputImages.value, ...uploaded]
    }
  } catch (e) {
    console.error('上传图片失败', e)
    proxy.$modal.msgError('上传图片失败')
  } finally {
    proxy.$modal.closeLoading()
  }
}
</script>

<style scoped lang="scss">
@use './input-area.scss';
</style>
