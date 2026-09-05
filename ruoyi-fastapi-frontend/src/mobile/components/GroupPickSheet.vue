<template>
  <Teleport to="body">
    <div v-if="modelValue" class="m-sheet-mask" @click="onMask">
      <div class="m-sheet" role="dialog" @click.stop>
        <div class="m-sheet__h">{{ title }}</div>
        <p v-if="hint" class="m-sheet__hint">{{ hint }}</p>
        <div v-if="groups.length" class="m-chip-row m-chip-row--sheet">
          <button
            v-for="g in groups"
            :key="g.name"
            type="button"
            class="m-chip"
            :class="{ 'is-on': picked === g.name }"
            @click="pickChip(g.name)"
          >{{ g.name }}<span v-if="g.count" class="m-chip__n">{{ g.count }}</span></button>
        </div>
        <label class="m-sheet__field">
          <span>新建分组</span>
          <input v-model="created" type="text" maxlength="32" placeholder="写入 note，逗号可多分" @input="onCreate" />
        </label>
        <div class="m-sheet__btns">
          <button v-if="allowSkip" type="button" @click="skip">跳过</button>
          <button type="button" class="primary" @click="confirm">确定</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { noteFromGroup } from '../utils/watchlist'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  groups: { type: Array, default: () => [] },
  title: { type: String, default: '加入分组' },
  hint: { type: String, default: '选已有分组或新建，确定后再加入自选' },
  allowSkip: { type: Boolean, default: true }
})
const emit = defineEmits(['update:modelValue', 'pick', 'skip'])

const picked = ref('')
const created = ref('')

watch(() => props.modelValue, (open) => {
  if (open) {
    picked.value = ''
    created.value = ''
  }
})

function pickChip(name) {
  created.value = ''
  picked.value = name
}

function onCreate() {
  if (created.value.trim()) picked.value = ''
}

function close() {
  emit('update:modelValue', false)
}

function currentNote() {
  return noteFromGroup(created.value || picked.value)
}

function confirm() {
  emit('pick', currentNote())
  close()
}

function skip() {
  emit('skip')
  emit('pick', '')
  close()
}

function onMask() {
  if (props.allowSkip) skip()
}
</script>
