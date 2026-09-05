<template>
  <div class="m-empty">
    <p>{{ message || '暂无数据' }}</p>
    <button v-if="retry" type="button" class="m-retry" @click="$emit('retry')">{{ retryText }}</button>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '' },
  retry: { type: Boolean, default: false },
  retryText: { type: String, default: '重试' }
})
defineEmits(['retry'])
</script>
