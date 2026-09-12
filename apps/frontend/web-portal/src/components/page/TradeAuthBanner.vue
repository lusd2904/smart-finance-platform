<template>
  <div v-if="visible" class="trade-auth-banner glass-panel">
    <div class="copy">
      <strong>长桥 OpenAPI 拒绝了 Access Token</strong>
      <p>
        券商返回 401004<span v-if="code && String(code) !== '401004'">（{{ code }}）</span>：纸交易账户 token 不被该接口接受或已失效。
        这不是本站登录过期，无需刷新平台 JWT。请到量化 · 长桥配置更换有效的长桥 Access Token。
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
