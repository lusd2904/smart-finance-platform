<template>
  <div class="app-container strategy-config-page">
    <div class="page-hero">
      <div>
        <h2>策略配置</h2>
        <p>本登录账户的交易开关与生效策略。定时扫描、自动交易、次日清单使用「生效」档及其权重；未配置长桥 Key 时默认关闭自动交易。</p>
      </div>
      <el-button :loading="loading" @click="reloadAll">刷新</el-button>
    </div>

    <el-card shadow="never" class="account-card mb16" v-loading="tradeLoading">
      <template #header>
        <div class="hdr">
          <span>本账户自动交易</span>
          <el-tag :type="tradeStatus.configured ? 'success' : 'warning'" effect="plain">
            {{ tradeStatus.configured ? '长桥 Key 已配置' : '未配置长桥 Key' }}
          </el-tag>
        </div>
      </template>
      <el-alert
        class="mb16"
        :type="tradeStatus.configured ? 'info' : 'warning'"
        show-icon
        :closable="false"
        :title="tradeStatus.configured
          ? '打开后，本账户的定时扫描与止损会向长桥真实下单，不会只写预警。'
          : '未配置长桥账户 Key，无法打开自动交易。请先到「量化交易 / 长桥配置」填写凭据。'"
      />
      <el-form label-width="140px">
        <el-form-item label="自动交易">
          <el-switch
            :model-value="!!tradeStatus.autoTradeEnabled"
            :disabled="savingSwitch || !tradeStatus.configured || !!tradeStatus.halted"
            :loading="savingSwitch"
            active-text="开"
            inactive-text="关"
            @change="onToggleAutoTrade"
          />
        </el-form-item>
        <el-form-item label="紧急停机">
          <el-switch
            :model-value="!!tradeStatus.halted"
            :disabled="savingHalt"
            :loading="savingHalt"
            active-text="停机"
            inactive-text="正常"
            @change="onToggleHalt"
          />
          <div class="hint">打开后拦截本平台全部新委托（手工 / 自动 / 次日清单），撤单仍可用。</div>
        </el-form-item>
        <el-form-item label="日内买入仓位">
          <el-slider
            v-model="buyRatioPct"
            :min="5"
            :max="50"
            :step="5"
            show-input
            @change="onRatioChange"
          />
          <div class="hint">按当前账户净资产的百分比作为日内买入上限，默认 20%。</div>
        </el-form-item>
        <el-form-item label="单标的仓位上限">
          <el-slider
            v-model="symbolCapPct"
            :min="5"
            :max="30"
            :step="5"
            show-input
            @change="onRatioChange"
          />
          <div class="hint">同一只股票持仓市值不超过净资产的该比例；当日已买入的标的不会因再次扫描重复下单。</div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16">
      <el-col :md="8" :xs="24" v-for="p in profiles" :key="p.profileCode">
        <el-card shadow="never" class="mb12">
          <template #header>
            <div class="hdr">
              <span class="hdr-title">
                {{ p.profileName }} ({{ p.profileCode }})
                <el-tag size="small" :type="p.active ? 'warning' : 'info'" effect="plain">
                  {{ p.active ? '生效中' : '未生效' }}
                </el-tag>
                <el-tag size="small" :type="p.accountOwned ? 'success' : 'info'" effect="plain">
                  {{ p.accountOwned ? '本账户权重' : '系统默认' }}
                </el-tag>
              </span>
              <span>
                <el-button size="small" :disabled="p.active || binding" @click="bind(p)">设为生效</el-button>
                <el-button size="small" type="primary" @click="save(p)">保存档位</el-button>
              </span>
            </div>
          </template>
          <el-form label-width="90px" size="small">
            <el-form-item label="买入阈值"><el-input-number v-model="p.config.buyThreshold" :min="0" :max="100" /></el-form-item>
            <el-form-item label="卖出阈值"><el-input-number v-model="p.config.sellThreshold" :min="0" :max="100" /></el-form-item>
            <el-form-item v-for="fam in families" :key="fam.key" :label="fam.label">
              <el-slider v-model="p.config.weights[fam.key]" :min="0" :max="1" :step="0.05" show-input />
            </el-form-item>
          </el-form>
          <div class="muted">更新：{{ p.updateTime || '--' }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="QuantStrategyConfig">
import { ElMessageBox } from 'element-plus'
import { listStrategyProfiles, saveStrategyProfile, bindStrategyProfile, getAutoTradeStatus, saveAutoTradeSettings, setTradeHalt } from '@/api/trade'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const tradeLoading = ref(false)
const savingSwitch = ref(false)
const savingHalt = ref(false)
const binding = ref(false)
const profiles = ref([])
const tradeStatus = ref({})
const buyRatioPct = ref(20)
const symbolCapPct = ref(10)
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

async function loadProfiles() {
  loading.value = true
  try {
    const res = await listStrategyProfiles()
    profiles.value = (res.data || []).map(p => ({ ...p, config: normalizeConfig(p.config) }))
  } finally {
    loading.value = false
  }
}

async function loadTrade() {
  tradeLoading.value = true
  try {
    const res = await getAutoTradeStatus()
    tradeStatus.value = res.data || {}
    const ratio = Number(tradeStatus.value.guardrails?.dailyBuyRatio || 0.2)
    buyRatioPct.value = Math.round(ratio * 100)
    const symbolPct = Number(tradeStatus.value.guardrails?.maxSymbolPositionPct || 0.1)
    symbolCapPct.value = Math.round(symbolPct * 100)
  } catch {
    tradeStatus.value = { configured: false, autoTradeEnabled: false }
  } finally {
    tradeLoading.value = false
  }
}

function reloadAll() {
  loadProfiles()
  loadTrade()
}

function settingsPayload(enabled) {
  return {
    autoTradeEnabled: Boolean(enabled),
    dailyBuyRatio: Number(buyRatioPct.value) / 100,
    maxSymbolPositionPct: Number(symbolCapPct.value) / 100
  }
}

async function onToggleHalt(val) {
  if (val) {
    try {
      await ElMessageBox.confirm(
        '打开后本平台所有新委托都会被拦截（手工下单、自动交易、次日清单）。撤单不受影响。确认停机？',
        '紧急停机',
        { type: 'warning', confirmButtonText: '确认停机', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  savingHalt.value = true
  try {
    const res = await setTradeHalt({ halted: Boolean(val), reason: val ? '策略配置页手动停机' : '' })
    tradeStatus.value = { ...tradeStatus.value, halted: Boolean(res.data?.halted), haltReason: res.data?.reason || '' }
    proxy.$modal.msgSuccess(res.msg || (val ? '已紧急停机' : '已解除停机'))
  } catch (err) {
    proxy.$modal.msgWarning(err.message || '停机开关保存失败')
  } finally {
    savingHalt.value = false
    loadTrade()
  }
}

async function onToggleAutoTrade(val) {
  if (val && !tradeStatus.value.configured) {
    proxy.$modal.msgWarning('未配置长桥账户 Key，无法打开自动交易')
    return
  }
  if (val) {
    try {
      await ElMessageBox.confirm(
        '打开后，本登录账户的定时扫描和止损将向长桥真实下单。确认打开？',
        '开启本账户自动交易',
        { type: 'warning', confirmButtonText: '确认打开', cancelButtonText: '取消' }
      )
    } catch {
      return
    }
  }
  savingSwitch.value = true
  try {
    const res = await saveAutoTradeSettings(settingsPayload(val))
    tradeStatus.value = res.data || tradeStatus.value
    proxy.$modal.msgSuccess(res.msg || '已保存本账户自动交易设置')
  } catch (err) {
    proxy.$modal.msgWarning(err.message || '未配置长桥账户 Key，无法打开自动交易')
  } finally {
    savingSwitch.value = false
    loadTrade()
  }
}

async function onRatioChange() {
  if (!tradeStatus.value.autoTradeEnabled && !tradeStatus.value.configured) return
  try {
    const res = await saveAutoTradeSettings(settingsPayload(!!tradeStatus.value.autoTradeEnabled))
    tradeStatus.value = res.data || tradeStatus.value
  } catch (err) {
    proxy.$modal.msgWarning(err.message || '仓位比例保存失败')
  }
}

async function save(p) {
  await saveStrategyProfile(p.profileCode, { profileName: p.profileName, config: p.config })
  proxy.$modal.msgSuccess('已保存本账户策略档位')
  loadProfiles()
}

async function bind(p) {
  binding.value = true
  try {
    await bindStrategyProfile(p.profileCode)
    proxy.$modal.msgSuccess('已绑定本账户生效策略：' + (p.profileName || p.profileCode))
    await loadProfiles()
  } finally {
    binding.value = false
  }
}

onMounted(reloadAll)
</script>

<style scoped>
.page-hero { display: flex; justify-content: space-between; margin-bottom: 16px; }
.page-hero h2 { margin: 0 0 4px; color: var(--text-emphasis); }
.page-hero p { margin: 0; color: var(--text-muted); font-size: 13px; }
.hdr { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.hdr-title { display: inline-flex; align-items: center; gap: 8px; }
.mb12 { margin-bottom: 12px; }
.mb16 { margin-bottom: 16px; }
.muted { font-size: 12px; color: var(--text-muted); }
.hint { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.account-card { max-width: 760px; }
</style>
