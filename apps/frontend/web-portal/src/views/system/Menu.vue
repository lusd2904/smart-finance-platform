<template>
  <PageFrame
    title="菜单管理"
    subtitle="工具栏 · 排序 · 可见"
    badge="「菜单管理 /system/menu」"
    :loading="loading"
  >
    <template #actions>
      <el-input v-model="keyword" clearable placeholder="搜索菜单 / 路径" style="width:200px" :prefix-icon="Search" />
      <el-button @click="expandAll">展开全部</el-button>
      <el-button type="primary" @click="openAdd()">+ 新建菜单</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · 对齐 menus.js · GET /system/menu/list" type="warning" show-icon :closable="false" />

    <el-card shadow="never" class="glass-panel">
      <el-table
        ref="tableRef"
        :data="filtered"
        stripe
        row-key="menuId"
        :default-expand-all="expanded"
        :tree-props="{ children: 'children' }"
        empty-text="暂无菜单"
      >
        <el-table-column prop="menuName" label="名称" min-width="200" />
        <el-table-column label="路径" min-width="180">
          <template #default="{ row }"><span class="numeric">{{ row.path || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="图标" width="110">
          <template #default="{ row }">{{ row.icon || '--' }}</template>
        </el-table-column>
        <el-table-column label="排序" width="72" align="right">
          <template #default="{ row }"><span class="numeric">{{ row.orderNum ?? row.sort ?? '--' }}</span></template>
        </el-table-column>
        <el-table-column label="可见" width="72">
          <template #default="{ row }">{{ isVisible(row) ? '可见' : '隐藏' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="148">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openAdd(row)">子项</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dlg" :title="form.menuId ? '编辑菜单' : '新建菜单'" width="440px">
      <el-form label-width="72px">
        <el-form-item label="名称"><el-input v-model="form.menuName" /></el-form-item>
        <el-form-item label="路径"><el-input v-model="form.path" placeholder="/market/heat" /></el-form-item>
        <el-form-item label="图标"><el-input v-model="form.icon" placeholder="Histogram" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.orderNum" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="可见">
          <el-switch v-model="form.visible" active-value="0" inactive-value="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>path 稳定 · 对齐 menus.js · 薄 CRUD · 勿盲扩 UI</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { addMenu, getMenu, listMenu, updateMenu } from '@/api/system'
import { unwrap } from '@/utils/list'
import { menuTree } from '@/config/menus'
import { unwrapList } from '@/utils/list'

const loading = ref(false)
const saving = ref(false)
const usingStub = ref(false)
const keyword = ref('')
const expanded = ref(true)
const tree = ref([])
const tableRef = ref(null)
const dlg = ref(false)
const form = reactive(emptyForm())

function emptyForm(parent) {
  return {
    menuId: undefined,
    parentId: parent?.menuId,
    menuName: '',
    path: '',
    icon: '',
    orderNum: 0,
    visible: '0'
  }
}

function isVisible(row) {
  return String(row.visible ?? '0') === '0'
}

function fromMenuTree() {
  let id = 1
  return menuTree.map((sub, i) => {
    const parentId = id++
    const children = []
    for (const group of sub.groups || []) {
      const leaves = (group.items || []).map((item, j) => ({
        menuId: id++,
        parentId,
        menuName: item.title,
        path: item.path,
        icon: item.icon,
        orderNum: j + 1,
        visible: '0'
      }))
      if ((sub.groups || []).length > 1 && group.title) {
        const gid = id++
        children.push({
          menuId: gid,
          parentId,
          menuName: group.title,
          path: '',
          icon: '',
          orderNum: children.length + 1,
          visible: '0',
          children: leaves.map((leaf) => ({ ...leaf, parentId: gid }))
        })
      } else {
        children.push(...leaves)
      }
    }
    return {
      menuId: parentId,
      menuName: sub.title,
      path: sub.path,
      icon: sub.icon,
      orderNum: i + 1,
      visible: '0',
      children
    }
  })
}

function toTree(rows) {
  const map = new Map(rows.map((r) => [r.menuId, { ...r, children: [] }]))
  const roots = []
  for (const node of map.values()) {
    if (node.parentId && map.has(node.parentId)) map.get(node.parentId).children.push(node)
    else roots.push(node)
  }
  return roots
}

function flatten(nodes, acc = []) {
  for (const n of nodes || []) {
    acc.push(n)
    if (n.children?.length) flatten(n.children, acc)
  }
  return acc
}

function matchNode(n, kw) {
  return `${n.menuName} ${n.path || ''}`.toLowerCase().includes(kw)
}

function filterTree(nodes, kw) {
  if (!kw) return nodes
  return nodes
    .map((n) => {
      const kids = filterTree(n.children || [], kw)
      if (matchNode(n, kw) || kids.length) return { ...n, children: kids }
      return null
    })
    .filter(Boolean)
}

const filtered = computed(() => filterTree(tree.value, keyword.value.trim().toLowerCase()))

function expandAll() {
  expanded.value = true
  nextTick(() => {
    flatten(tree.value).forEach((row) => tableRef.value?.toggleRowExpansion(row, true))
  })
}

async function load() {
  loading.value = true
  try {
    const rows = unwrapList(await listMenu({}))
    if (rows.length) {
      tree.value = rows.some((r) => r.children?.length) ? rows : toTree(rows)
      usingStub.value = false
    } else {
      tree.value = fromMenuTree()
      usingStub.value = true
    }
  } catch {
    tree.value = fromMenuTree()
    usingStub.value = true
  } finally {
    loading.value = false
    nextTick(expandAll)
  }
}

function openAdd(parent) {
  Object.assign(form, emptyForm(parent))
  dlg.value = true
}

async function openEdit(row) {
  Object.assign(form, {
    menuId: row.menuId,
    parentId: row.parentId,
    menuName: row.menuName,
    path: row.path || '',
    icon: row.icon || '',
    orderNum: Number(row.orderNum || 0),
    visible: isVisible(row) ? '0' : '1'
  })
  dlg.value = true
  if (usingStub.value || !row.menuId) return
  try {
    const data = unwrap(await getMenu(row.menuId))
    if (data?.menuName || data?.path) {
      Object.assign(form, {
        menuId: data.menuId ?? form.menuId,
        parentId: data.parentId ?? form.parentId,
        menuName: data.menuName || form.menuName,
        path: data.path || form.path,
        icon: data.icon || form.icon,
        orderNum: Number(data.orderNum ?? form.orderNum),
        visible: isVisible(data) ? '0' : '1'
      })
    }
  } catch {
    /* keep row snapshot */
  }
}

async function save() {
  if (!form.menuName.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    if (form.menuId) await updateMenu({ ...form })
    else await addMenu({ ...form })
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
