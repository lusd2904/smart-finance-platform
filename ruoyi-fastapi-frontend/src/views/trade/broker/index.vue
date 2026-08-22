<template>
  <div class="app-container">
    <div class="page-hero"><div><h2>券商账户</h2><p>当前平台优先接入长桥；多券商可在此扩展</p></div>
      <el-button type="primary" @click="$router.push('/quant/longbridge')">管理长桥凭证</el-button></div>
    <el-row :gutter="16">
      <el-col :md="8" :xs="24">
        <el-card shadow="never" class="broker-card">
          <div class="name">Longbridge 长桥</div>
          <div class="desc">行情 · 持仓 · 下单 · 订单</div>
          <el-tag :type="configured?'success':'info'">{{ configured?'已配置':'未配置' }}</el-tag>
          <div class="acts">
            <el-button size="small" @click="test">连通测试</el-button>
            <el-button size="small" type="primary" @click="$router.push('/trade/trading')">进入交易台</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-card shadow="never" class="broker-card disabled">
          <div class="name">Tiger 老虎</div>
          <div class="desc">规划中</div>
          <el-tag type="info">未接入</el-tag>
        </el-card>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-card shadow="never" class="broker-card disabled">
          <div class="name">富途 OpenAPI</div>
          <div class="desc">规划中</div>
          <el-tag type="info">未接入</el-tag>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup name="TradeBroker">
import { getLongbridgeConfig, testLongbridge } from '@/api/quant'
const {proxy}=getCurrentInstance(); const configured=ref(false)
async function load(){ try{ const res=await getLongbridgeConfig(); const d=res.data||{}; configured.value=!!(d.appKey||d.configured) } catch { /* 配置缺失时保持默认未配置状态 */ } }
async function test(){ const res=await testLongbridge(); const d=res.data||{}; proxy.$modal.msgSuccess(d.message||JSON.stringify(d)) }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.broker-card{margin-bottom:12px;min-height:160px} .broker-card.disabled{opacity:.55}
.name{font-size:18px;font-weight:700;color:var(--text-emphasis);margin-bottom:6px}
.desc{color:var(--text-muted);font-size:13px;margin-bottom:12px} .acts{margin-top:14px;display:flex;gap:8px}
</style>
