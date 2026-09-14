<template>
  <PageFrame
    title="角色管理"
    subtitle="角色列表 · 权限摘要"
    :loading="loading"
  >
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="角色" style="width:180px" :prefix-icon="Search" @keyup.enter="load" />
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-button type="primary" @click="openAdd">+ 新建角色</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · GET /system/role/list" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <el-card shadow="never" class="glass-panel">
      <el-table :data="filtered" stripe highlight-current-row empty-text="暂无角色" @row-click="select">
        <el-table-column type="index" label="#" width="52" />
        <el-table-column prop="roleName" label="角色" min-width="140" />
        <el-table-column label="权限摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ summaryText(row) }}</template>
        </el-table-column>
        <el-table-column label="绑定用户数" width="110" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.userCount ?? row.userNum ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="128">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="select(row)">权限</el-button>
            <el-button link type="primary" @click.stop="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="glass-panel">
      <template #header>
        <div class="card-head">
          <h3>权限矩阵 · {{ current ? current.roleName : '选择角色' }}</h3>
          <span class="muted">芯片只读摘要 · 非完整 RBAC 工作台</span>
        </div>
      </template>
      <div v-if="current" class="matrix">
        <section v-for="group in matrix" :key="group.title">
          <h4>{{ group.title }}</h4>
          <div class="chip-row">
            <span v-for="item in group.items" :key="item" class="filter-chip" :class="{ active: hasPerm(item) }">{{ item }}</span>
          </div>
        </section>
      </div>
      <el-empty v-else description="选择一行查看权限摘要" :image-size="56" />
    </el-card>

    <el-dialog v-model="dlg" :title="form.roleId ? '编辑角色' : '新建角色'" width="420px">
      <el-form label-width="72px">
        <el-form-item label="角色"><el-input v-model="form.roleName" /></el-form-item>
        <el-form-item label="权限字"><el-input v-model="form.roleKey" placeholder="admin / trader" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>tabular-nums · glass-panel · 薄 CRUD · GET /system/role/list</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { addRole, listRole, updateRole } from '@/api/system'
import { unwrapList } from '@/utils/list'
import { useUserStore } from '@/store/user'
import { errorText, isDemoSession, stubRoles } from '@/utils/stubs'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const GROUPS = [
  { title: '系统管理', items: ['用户', '角色', '菜单'] },
  { title: '行情 / 分析', items: ['看板', '自选', '任务中心'] },
  { title: '交易', items: ['持仓', '委托', '风控'] },
  { title: 'AI / 量化', items: ['模型', '研判', '因子'] }
]

const loading = ref(false)
const saving = ref(false)
const usingStub = ref(false)
const loadError = ref('')
const keyword = ref('')
const list = ref([])
const current = ref(null)
const dlg = ref(false)
const form = reactive({ roleId: undefined, roleName: '', roleKey: '', remark: '' })

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return list.value
  return list.value.filter((r) => `${r.roleName} ${r.roleKey} ${r.remark || ''}`.toLowerCase().includes(kw))
})

const matrix = GROUPS

function permsOf(row) {
  if (!row) return []
  if (Array.isArray(row.menus) && row.menus.length) return row.menus
  const key = String(row.roleKey || row.roleName || '').toLowerCase()
  if (key.includes('admin') || row.roleName === '超级管理员') return GROUPS.flatMap((g) => g.items)
  if (key.includes('trade')) return ['看板', '自选', '持仓', '委托', '风控']
  if (key.includes('analy') || key.includes('分析')) return ['看板', '自选', '任务中心', '研判']
  if (key.includes('quant') || key.includes('量化')) return ['看板', '因子', '模型', '研判']
  if (key.includes('risk') || key.includes('风控')) return ['持仓', '委托', '风控']
  if (key.includes('view') || key.includes('只读')) return ['看板']
  return String(row.remark || '').split(/[,，、\s]+/).filter(Boolean)
}

function hasPerm(item) {
  return permsOf(current.value).includes(item)
}

function summaryText(row) {
  const perms = permsOf(row)
  return perms.length ? perms.slice(0, 6).join(' / ') : (row.roleKey || row.remark || '--')
}

function select(row) {
  current.value = row
}

function openAdd() {
  Object.assign(form, { roleId: undefined, roleName: '', roleKey: '', remark: '' })
  dlg.value = true
}

function openEdit(row) {
  Object.assign(form, { roleId: row.roleId, roleName: row.roleName, roleKey: row.roleKey, remark: row.remark || '' })
  dlg.value = true
}

async function load() {
  if (demoMode()) {
    applyStub()
    return
  }
  loading.value = true
  usingStub.value = false
  loadError.value = ''
  try {
    const rows = unwrapList(await listRole({ pageNum: 1, pageSize: 50, roleName: keyword.value || undefined }))
    list.value = rows
    current.value = rows[0] || null
  } catch (e) {
    list.value = []
    current.value = null
    loadError.value = errorText(e, '角色加载失败')
  } finally {
    loading.value = false
  }
}

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  loadError.value = ''
  list.value = stubRoles()
  current.value = list.value[0]
}

async function save() {
  if (!form.roleName.trim()) {
    ElMessage.warning('请填写角色名')
    return
  }
  saving.value = true
  try {
    if (form.roleId) await updateRole({ ...form })
    else await addRole({ ...form })
    ElMessage.success('已保存')
    dlg.value = false
    load()
  } catch (e) {
    if (usingStub.value) {
      ElMessage.success('已保存（STUB）')
      dlg.value = false
    } else ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
h3, h4 { margin: 0; }
h4 { font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
.matrix { display: grid; gap: 12px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.muted { color: var(--text-secondary); font-size: 12px; }
</style>
