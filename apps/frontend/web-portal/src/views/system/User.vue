<template>
  <PageFrame
    title="用户管理"
    subtitle="筛选 · KPI · 用户表"
    :loading="loading"
  >
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="用户名 / 昵称" style="width:180px" :prefix-icon="Search" @keyup.enter="onFilter" />
      <el-radio-group v-model="status" @change="onFilter">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="ok">正常</el-radio-button>
        <el-radio-button value="lock">锁定</el-radio-button>
        <el-radio-button value="off">停用</el-radio-button>
      </el-radio-group>
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-button type="primary" @click="openAdd">+ 新建用户</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · GET /system/user/list" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <div class="stat-strip">
      <article class="stat-tile glass-panel"><span>用户总数</span><strong class="numeric">{{ kpis.total }}</strong></article>
      <article class="stat-tile glass-panel"><span>今日活跃</span><strong class="numeric">{{ kpis.active }}</strong></article>
      <article class="stat-tile glass-panel"><span>角色种类</span><strong class="numeric">{{ kpis.roles }}</strong></article>
      <article class="stat-tile glass-panel">
        <span>锁定 / 停用</span>
        <strong class="numeric"><em class="down">{{ kpis.locked }}</em> / <em class="down">{{ kpis.off }}</em></strong>
      </article>
    </div>

    <el-card shadow="never" class="glass-panel">
      <el-table :data="list" stripe empty-text="暂无用户">
        <el-table-column type="index" label="#" width="52" :index="indexOf" />
        <el-table-column prop="userName" label="用户名" min-width="140" />
        <el-table-column prop="nickName" label="昵称" min-width="120" show-overflow-tooltip />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">{{ roleText(row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row)" effect="plain">{{ statusLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="170">
          <template #default="{ row }"><span class="numeric">{{ row.loginDate || row.loginTime || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="168">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="resetPwd(row)">重置</el-button>
            <el-dropdown>
              <el-button link type="primary">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="toggleStatus(row)">{{ isOff(row) ? '启用' : '停用' }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="dlg" :title="form.userId ? '编辑用户' : '新建用户'" width="440px">
      <el-form label-width="72px">
        <el-form-item label="用户名"><el-input v-model="form.userName" :disabled="Boolean(form.userId)" /></el-form-item>
        <el-form-item label="昵称"><el-input v-model="form.nickName" /></el-form-item>
        <el-form-item v-if="!form.userId" label="密码"><el-input v-model="form.password" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio-button value="0">正常</el-radio-button>
            <el-radio-button value="1">停用</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>tabular-nums · glass-panel · 启用绿 / 停用红 · GET /system/user/list</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { addUser, changeUserStatus, listUser, resetUserPwd, updateUser } from '@/api/system'
import { unwrap, unwrapList, unwrapTotal } from '@/utils/list'
import { useUserStore } from '@/store/user'
import { errorText, isDemoSession, stubUsers } from '@/utils/stubs'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const loading = ref(false)
const saving = ref(false)
const usingStub = ref(false)
const loadError = ref('')
const keyword = ref('')
const status = ref('')
const list = ref([])
const allRows = ref([])
const page = ref(1)
const total = ref(0)
const dlg = ref(false)
const form = reactive({ userId: undefined, userName: '', nickName: '', password: '', status: '0' })

function isLocked(row) {
  return String(row.lockFlag || row.locked || '') === '1' || row.status === '2'
}
function isOff(row) {
  return String(row.status) === '1'
}
function statusKey(row) {
  if (isOff(row)) return 'off'
  if (isLocked(row)) return 'lock'
  return 'ok'
}
function statusLabel(row) {
  return { ok: '正常', lock: '锁定', off: '停用' }[statusKey(row)]
}
function statusType(row) {
  return { ok: 'success', lock: 'warning', off: 'danger' }[statusKey(row)]
}
function roleText(row) {
  if (row.roleName) return row.roleName
  const roles = row.roles || row.roleNames || []
  if (Array.isArray(roles)) return roles.map((r) => r.roleName || r).filter(Boolean).join('、') || '--'
  return row.roleKey || '--'
}
function indexOf(i) {
  return (page.value - 1) * 20 + i + 1
}
function isToday(text) {
  const raw = String(text || '')
  if (!raw) return false
  const today = new Date().toISOString().slice(0, 10)
  return raw.startsWith(today) || raw.includes('今天')
}

const kpis = computed(() => {
  const rows = allRows.value.length ? allRows.value : list.value
  const roles = new Set(rows.map(roleText).filter((n) => n && n !== '--'))
  return {
    total: total.value || rows.length,
    active: rows.filter((r) => isToday(r.loginDate || r.loginTime)).length,
    roles: roles.size,
    locked: rows.filter(isLocked).length,
    off: rows.filter(isOff).length
  }
})

function onFilter() {
  page.value = 1
  load()
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
    const res = await listUser({
      pageNum: page.value,
      pageSize: 20,
      userName: keyword.value || undefined,
      nickName: keyword.value || undefined,
      status: status.value === 'off' ? '1' : status.value === 'ok' ? '0' : undefined
    })
    let rows = unwrapList(res)
    const data = unwrap(res)
    if (data.users) rows = data.users
    if (status.value === 'lock') rows = rows.filter(isLocked)
    list.value = rows
    allRows.value = data.all || rows
    total.value = unwrapTotal(res, rows.length)
  } catch (e) {
    list.value = []
    allRows.value = []
    total.value = 0
    loadError.value = errorText(e, '用户列表加载失败')
  } finally {
    loading.value = false
  }
}

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  loadError.value = ''
  const rows = stubUsers().filter((r) => {
    const kw = keyword.value.trim().toLowerCase()
    const textOk = !kw || `${r.userName} ${r.nickName}`.toLowerCase().includes(kw)
    const stOk = !status.value || statusKey(r) === status.value
    return textOk && stOk
  })
  list.value = rows
  allRows.value = stubUsers()
  total.value = rows.length
}

function openAdd() {
  Object.assign(form, { userId: undefined, userName: '', nickName: '', password: '', status: '0' })
  dlg.value = true
}
function openEdit(row) {
  Object.assign(form, { userId: row.userId, userName: row.userName, nickName: row.nickName, password: '', status: isOff(row) ? '1' : '0' })
  dlg.value = true
}

async function save() {
  if (!form.userName.trim()) {
    ElMessage.warning('请填写用户名')
    return
  }
  saving.value = true
  try {
    if (form.userId) await updateUser({ userId: form.userId, userName: form.userName, nickName: form.nickName, status: form.status })
    else await addUser({ userName: form.userName, nickName: form.nickName, password: form.password, status: form.status })
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
    form.password = ''
  }
}

async function resetPwd(row) {
  const { value } = await ElMessageBox.prompt(`重置 ${row.userName} 的密码`, '重置密码', { inputType: 'password' })
  if (!value) return
  try {
    await resetUserPwd(row.userId, value)
    ElMessage.success('已重置')
  } catch (e) {
    ElMessage[usingStub.value ? 'success' : 'error'](usingStub.value ? '已重置（STUB）' : (e?.message || '失败'))
  }
}

async function toggleStatus(row) {
  const next = isOff(row) ? '0' : '1'
  try {
    await changeUserStatus(row.userId, next)
    row.status = next
    ElMessage.success('已更新')
  } catch (e) {
    if (usingStub.value) {
      row.status = next
      ElMessage.success('已更新（STUB）')
    } else ElMessage.error(e?.message || '失败')
  }
}

onMounted(load)
</script>

<style scoped>
.stat-strip em { font-style: normal; }
.pager { display: flex; justify-content: flex-end; padding-top: 10px; }
</style>
