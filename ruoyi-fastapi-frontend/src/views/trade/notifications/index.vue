<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>通知中心</h2><p>交易、回测与系统事件</p></div>
      <div>
        <el-button @click="markAll">全部已读</el-button>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <el-timeline v-if="list.length">
      <el-timeline-item v-for="n in list" :key="n.id" :type="typeMap[n.level]||'primary'" :timestamp="n.createTime" placement="top">
        <div class="n-title" :class="{unread:!n.read}">{{ n.title }} <el-tag size="small" effect="plain">{{ n.category }}</el-tag></div>
        <div class="n-body">{{ n.content }}</div>
        <el-button v-if="!n.read" link type="primary" @click="mark(n)">标为已读</el-button>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-else description="暂无通知"/>
  </div>
</template>
<script setup name="TradeNotifications">
import { listNotifications, readNotifications } from '@/api/trade'
const loading=ref(false); const list=ref([])
const typeMap={success:'success', danger:'danger', warning:'warning', info:'primary'}
async function load(){ loading.value=true; try{ const res=await listNotifications(80); list.value=res.data||[] } finally{ loading.value=false } }
async function mark(n){ await readNotifications(n.id); load() }
async function markAll(){ await readNotifications(); load() }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
.n-title{font-weight:600;color:var(--text-emphasis);margin-bottom:4px} .n-title.unread{color:var(--accent,#6366f1)}
.n-body{color:var(--text-secondary);font-size:13px;line-height:1.6}
</style>
