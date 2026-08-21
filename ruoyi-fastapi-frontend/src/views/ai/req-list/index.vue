<template>
  <div class="app-container">
    <div class="page-hero">
      <div>
        <h2>AI 需求清单</h2>
        <p>群里确认后由 Grok 写入。开发上线并测试通过后，在这里手动改状态。可用对外接口本地拉取再改代码提交 git。</p>
      </div>
      <div class="acts">
        <el-select v-model="status" clearable placeholder="状态" style="width:140px" @change="load">
          <el-option label="全部" value="" />
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button @click="copyExport">复制登录导出命令</el-button>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <el-alert
      class="mb16"
      type="info"
      show-icon
      :closable="false"
      title="对外接口：GET /open/requirements ，Header X-Req-Token 填环境变量 REQUIREMENTS_EXPORT_TOKEN。可带 ?status=pending"
    />
    <el-table v-loading="loading" :data="items" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column prop="title" label="优化点" min-width="180" />
      <el-table-column prop="detail" label="说明" min-width="240" show-overflow-tooltip />
      <el-table-column prop="statusLabel" label="状态" width="100">
        <template #default="{row}">
          <el-tag size="small" :type="statusTone(row.status)">{{ row.statusLabel }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdBy" label="来源" width="110" />
      <el-table-column prop="createTime" label="写入时间" width="170" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{row}">
          <el-select
            v-if="row.status !== 'done'"
            size="small"
            :model-value="row.status"
            style="width: 120px"
            @change="(val) => changeStatus(row, val)"
            v-hasPermi="['ai:req:edit']"
          >
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <span v-else class="muted">已完成</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup name="AiReqList">
import { listReqItems, updateReqStatus } from '@/api/ai/req'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const status = ref('')
const items = ref([])
const statusOptions = [
  { value: 'pending', label: '待开发' },
  { value: 'developing', label: '开发中' },
  { value: 'testing', label: '测试中' },
  { value: 'done', label: '已完成' },
  { value: 'cancelled', label: '已取消' }
]

function statusTone(s) {
  if (s === 'done') return 'success'
  if (s === 'testing') return 'warning'
  if (s === 'cancelled') return 'info'
  if (s === 'developing') return 'primary'
  return 'danger'
}

async function load() {
  loading.value = true
  try {
    const res = await listReqItems(status.value || undefined)
    items.value = (res.data && res.data.items) || []
  } finally {
    loading.value = false
  }
}

async function changeStatus(row, val) {
  await updateReqStatus(row.id, { status: val })
  proxy.$modal.msgSuccess('状态已更新')
  load()
}

function copyExport() {
  const text = 'curl -s -H "Authorization: Bearer <登录token>" http://127.0.0.1:19099/ai/req/items/export'
  navigator.clipboard.writeText(text).then(() => proxy.$modal.msgSuccess('已复制')).catch(() => {
    proxy.$modal.msg(text)
  })
}

onMounted(load)
</script>

<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.page-hero h2{margin:0 0 4px}
.page-hero p{margin:0;color:#909399;font-size:13px;max-width:640px}
.acts{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.mb16{margin-bottom:16px}
.muted{color:#94a3b8;font-size:12px}
</style>
