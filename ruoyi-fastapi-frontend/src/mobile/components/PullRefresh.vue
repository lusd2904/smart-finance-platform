<template>
  <div
    class="m-pull"
    @touchstart="onStart"
    @touchmove="onMove"
    @touchend="onEnd"
  >
    <div class="m-pull__hint" :style="{ height: hintH + 'px' }">
      <span v-if="refreshing">刷新中…</span>
      <span v-else-if="pull > 48">松开刷新</span>
      <span v-else-if="pull > 8">下拉刷新</span>
    </div>
    <div class="m-pull__body" :style="{ transform: `translateY(${offset}px)` }">
      <slot />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  refreshing: { type: Boolean, default: false }
})
const emit = defineEmits(['refresh'])

const pull = ref(0)
const startY = ref(0)
const dragging = ref(false)

const hintH = computed(() => {
  if (props.refreshing) return 36
  return Math.min(36, pull.value * 0.5)
})
const offset = computed(() => (props.refreshing ? 36 : Math.min(64, pull.value * 0.45)))

function scrollTop() {
  const el = document.scrollingElement || document.documentElement
  return el ? el.scrollTop : 0
}

function onStart(e) {
  if (props.refreshing || scrollTop() > 0) return
  dragging.value = true
  startY.value = e.touches[0].clientY
}

function onMove(e) {
  if (!dragging.value) return
  const dy = e.touches[0].clientY - startY.value
  pull.value = dy > 0 ? dy : 0
}

function onEnd() {
  if (!dragging.value) return
  dragging.value = false
  if (pull.value > 48 && !props.refreshing) emit('refresh')
  pull.value = 0
}

watch(() => props.refreshing, (v) => {
  if (!v) pull.value = 0
})
</script>

<style scoped lang="scss">
.m-pull {
  min-height: 100%;
}
.m-pull__hint {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
  color: #8b8d98;
  font-size: 12px;
}
.m-pull__body {
  min-height: 60vh;
}
</style>
