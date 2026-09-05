<template>
  <div class="m-swipe" :class="{ 'is-open': open }">
    <div class="m-swipe__actions">
      <button type="button" class="m-swipe__del" @click.stop="askDelete">删除</button>
    </div>
    <div
      class="m-swipe__front"
      :style="{ transform: `translateX(${offset}px)` }"
      @pointerdown="onStart"
      @pointermove="onMove"
      @pointerup="onEnd"
      @pointercancel="onEnd"
    >
      <QuoteRow
        :symbol="symbol"
        :name="name"
        :market="market"
        :last="last"
        :change-pct="changePct"
        :rank="rank"
        :in-watchlist="inWatchlist"
        :tag="tag"
        :tag-tone="tagTone"
        :subtitle="subtitle"
        @click="onClick"
        @longpress="onLong"
      />
    </div>
  </div>
</template>

<script setup>
import QuoteRow from './QuoteRow.vue'

defineProps({
  symbol: { type: String, default: '' },
  name: { type: String, default: '' },
  market: { type: String, default: '' },
  last: { type: [Number, String], default: null },
  changePct: { type: [Number, String], default: null },
  rank: { type: [Number, String], default: null },
  inWatchlist: { type: Boolean, default: false },
  tag: { type: String, default: '' },
  tagTone: { type: String, default: 'flat' },
  subtitle: { type: String, default: '' }
})
const emit = defineEmits(['click', 'delete'])

const REVEAL = 72
const startX = ref(0)
const startY = ref(0)
const dx = ref(0)
const dragging = ref(false)
const axis = ref('')
const open = ref(false)
const swiped = ref(false)

const offset = computed(() => {
  if (dragging.value && axis.value === 'x') {
    const base = open.value ? -REVEAL : 0
    return Math.max(-REVEAL, Math.min(0, base + dx.value))
  }
  return open.value ? -REVEAL : 0
})

function onStart(e) {
  startX.value = e.clientX
  startY.value = e.clientY
  dx.value = 0
  dragging.value = true
  axis.value = ''
  swiped.value = false
  if (e.currentTarget && e.currentTarget.setPointerCapture) {
    e.currentTarget.setPointerCapture(e.pointerId)
  }
}

function onMove(e) {
  if (!dragging.value) return
  const mx = e.clientX - startX.value
  const my = e.clientY - startY.value
  if (!axis.value) {
    if (Math.abs(mx) < 8 && Math.abs(my) < 8) return
    axis.value = Math.abs(mx) >= Math.abs(my) ? 'x' : 'y'
  }
  if (axis.value !== 'x') return
  dx.value = mx
  if (e.cancelable) e.preventDefault()
}

function onEnd() {
  if (!dragging.value) return
  dragging.value = false
  if (axis.value === 'x') {
    const next = offset.value <= -REVEAL / 2
    if (next !== open.value) swiped.value = true
    open.value = next
  }
  dx.value = 0
  axis.value = ''
}

function onClick() {
  if (open.value) {
    open.value = false
    return
  }
  if (swiped.value) {
    swiped.value = false
    return
  }
  emit('click')
}

function onLong() {
  if (Math.abs(offset.value) > 12) return
  emit('delete')
}

function askDelete() {
  emit('delete')
}

function close() {
  open.value = false
}

defineExpose({ close })
</script>

<style scoped lang="scss">
.m-swipe {
  position: relative;
  overflow: hidden;
  background: #e5484d;
}
.m-swipe__actions {
  position: absolute;
  inset: 0 0 0 auto;
  width: 72px;
  display: flex;
}
.m-swipe__del {
  flex: 1;
  border: 0;
  background: #e5484d;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}
.m-swipe__front {
  position: relative;
  background: #fff;
  will-change: transform;
  touch-action: pan-y;
}
.is-open .m-swipe__front {
  transition: transform 0.18s ease;
}
.m-swipe__front {
  transition: transform 0.18s ease;
}
</style>
