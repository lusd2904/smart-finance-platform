<template>
  <Teleport to="body">
    <div v-if="modelValue" class="m-sheet-mask" @click="cancel">
      <div class="m-sheet m-sheet--center" role="dialog" @click.stop>
        <p class="m-sheet__msg">{{ message }}</p>
        <div class="m-sheet__btns">
          <button type="button" @click="cancel">{{ cancelText }}</button>
          <button type="button" class="danger" @click="ok">{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  message: { type: String, default: '确认？' },
  confirmText: { type: String, default: '删除' },
  cancelText: { type: String, default: '取消' }
})
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

function cancel() {
  emit('update:modelValue', false)
  emit('cancel')
}

function ok() {
  emit('confirm')
  emit('update:modelValue', false)
}
</script>
