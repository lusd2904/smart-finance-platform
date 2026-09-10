<template>
  <div v-if="visible" class="trade-auth-banner glass-panel">
    <div class="copy">
      <strong>长桥凭证不可用</strong>
      <p>
        交易接口返回 401<span v-if="code">（{{ code }}）</span>。
        请到量化 · 长桥配置检查 App Key / Token。
        <template v-if="cached">当前展示的是缓存数据，勿当成实时空仓。</template>
      </p>
    </div>
    <el-button type="primary" @click="$router.push('/quant/longbridge')">去长桥配置</el-button>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  code: { type: [String, Number], default: '' },
  cached: { type: Boolean, default: false }
})
</script>

<style scoped>
.trade-auth-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
}
.copy {
  display: grid;
  gap: 4px;
  min-width: 0;
}
.copy strong { color: var(--text-emphasis); font-size: 13px; }
.copy p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
</style>
