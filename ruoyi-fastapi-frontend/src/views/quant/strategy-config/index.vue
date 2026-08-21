<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>策略配置</h2><p>档位阈值与因子权重持久化</p></div>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button></div>
    <el-row :gutter="16">
      <el-col :md="8" :xs="24" v-for="p in profiles" :key="p.profileCode">
        <el-card shadow="never" class="mb12">
          <template #header><div class="hdr"><span>{{ p.profileName }} ({{ p.profileCode }})</span>
            <el-button size="small" type="primary" @click="save(p)">保存</el-button></div></template>
          <el-form label-width="90px" size="small">
            <el-form-item label="买入阈值"><el-input-number v-model="p.config.buyThreshold" :min="0" :max="100"/></el-form-item>
            <el-form-item label="卖出阈值"><el-input-number v-model="p.config.sellThreshold" :min="0" :max="100"/></el-form-item>
            <el-form-item v-for="fam in families" :key="fam.key" :label="fam.label">
              <el-slider v-model="p.config.weights[fam.key]" :min="0" :max="1" :step="0.05" show-input/>
            </el-form-item>
          </el-form>
          <div class="muted">更新：{{ p.updateTime || '--' }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup name="QuantStrategyConfig">
import { listStrategyProfiles, saveStrategyProfile } from '@/api/trade'
const {proxy}=getCurrentInstance(); const loading=ref(false); const profiles=ref([])
const families = [
  { key: 'trend', label: '趋势' },
  { key: 'priceAction', label: '价型' },
  { key: 'momentum', label: '动量' },
  { key: 'breakout', label: '突破' },
  { key: 'volumeFlow', label: '量能' },
  { key: 'reversion', label: '回归' },
  { key: 'volatility', label: '波动' },
  { key: 'liquidity', label: '流动性' }
]
function normalizeConfig(cfg) {
  const config = { buyThreshold: 64, sellThreshold: 38, weights: {}, ...(cfg || {}) }
  const weights = { ...(config.weights || {}) }
  if (weights.volume != null && weights.volumeFlow == null) weights.volumeFlow = weights.volume
  if (weights.value != null && weights.reversion == null) weights.reversion = weights.value
  if (weights.quality != null && weights.liquidity == null) weights.liquidity = weights.quality
  families.forEach(f => { if (weights[f.key] == null) weights[f.key] = 0.1 })
  config.weights = weights
  return config
}
async function load(){ loading.value=true; try{ const res=await listStrategyProfiles(); profiles.value=(res.data||[]).map(p=>({...p, config: normalizeConfig(p.config)})) } finally{ loading.value=false } }
async function save(p){ await saveStrategyProfile(p.profileCode,{profileName:p.profileName, config:p.config}); proxy.$modal.msgSuccess('已保存'); load() }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;margin-bottom:16px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.hdr{display:flex;justify-content:space-between;align-items:center} .mb12{margin-bottom:12px} .muted{font-size:12px;color:var(--text-muted)}
</style>
