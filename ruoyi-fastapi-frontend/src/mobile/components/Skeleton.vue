<template>
  <div class="m-skel" :style="{ height: height + 'px', width: width }">
    <span v-for="n in rows" :key="n" />
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 6 },
  height: { type: Number, default: 16 },
  width: { type: String, default: '100%' }
})
</script>

<style scoped>
.m-skel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
}
.m-skel span {
  display: block;
  height: v-bind(height + 'px');
  border-radius: 6px;
  background: linear-gradient(90deg, #eef0f3 25%, #f7f8fa 37%, #eef0f3 63%);
  background-size: 400% 100%;
  animation: m-skel 1.2s ease infinite;
}
@keyframes m-skel {
  0% { background-position: 100% 0; }
  100% { background-position: 0 0; }
}
</style>
