<template>
  <section class="m-metrics-wrap">
    <div class="m-metrics">
      <div v-for="cell in core" :key="cell.key" class="m-metrics__cell">
        <div class="k">{{ cell.label }}</div>
        <div class="v m-num">{{ cell.text }}</div>
      </div>
    </div>
    <button v-if="extra.length" type="button" class="m-more" @click="$emit('toggle')">
      {{ expanded ? '收起' : '更多' }}
    </button>
    <div v-if="expanded && extra.length" class="m-metrics m-metrics--more">
      <div v-for="cell in extra" :key="cell.key" class="m-metrics__cell">
        <div class="k">{{ cell.label }}</div>
        <div class="v m-num">{{ cell.text }}</div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  core: { type: Array, default: () => [] },
  extra: { type: Array, default: () => [] },
  expanded: { type: Boolean, default: false }
})
defineEmits(['toggle'])
</script>

<style scoped lang="scss">
.m-metrics-wrap {
  background: #fff;
  border-bottom: 1px solid #ececef;
}
.m-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px 8px;
  padding: 10px 16px 8px;
}
.m-metrics__cell .k {
  color: #8b8d98;
  font-size: 11px;
}
.m-metrics__cell .v {
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
}
.m-more {
  display: block;
  width: 100%;
  height: 36px;
  border: 0;
  background: transparent;
  color: #409eff;
  font-size: 13px;
  font-weight: 600;
}
</style>
