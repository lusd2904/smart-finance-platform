<template>
  <PageFrame
    title="模型管理"
    subtitle="延迟 · 配额 · 默认模型 · 健康探测"
    :loading="loading"
  >
    <template #actions>
      <el-button :loading="probingAll" @click="probeAll">全部探测</el-button>
      <el-button type="primary" @click="openAdd">+ 添加模型</el-button>
    </template>

    <el-alert v-if="usingStub" title="STUB · 演示模型卡，字段缺失时的回退" type="warning" show-icon :closable="false" />
    <el-alert v-else-if="loadError" :title="loadError" type="error" show-icon :closable="false" />

    <div class="stat-strip kpi-5">
      <article class="stat-tile glass-panel">
        <span>已配置</span>
        <strong class="numeric">{{ kpis.total }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>启用 / 停用</span>
        <strong class="numeric">
          <em class="up">{{ kpis.enabled }}</em>
          <span> / </span>
          <em class="down">{{ kpis.disabled }}</em>
        </strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>默认 chat</span>
        <strong>{{ kpis.defaultName }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>平均延迟</span>
        <strong class="numeric">{{ kpis.avgLatency }}</strong>
      </article>
      <article class="stat-tile glass-panel">
        <span>健康状态</span>
        <strong :class="kpis.healthCls">{{ kpis.healthText }}</strong>
        <small class="muted numeric">{{ kpis.healthSub }}</small>
      </article>
    </div>

    <el-empty v-if="!loading && !rows.length" description="暂无模型，点击「添加模型」或检查 /ai/model/list" />

    <article v-for="row in rows" :key="row.modelId || row.modelCode" class="model-card glass-panel">
      <div class="card-top">
        <div>
          <strong>{{ row.modelName || row.modelCode || '--' }}</strong>
          <div class="meta muted">
            {{ row.provider || '--' }}
            <span> · </span>
            scope={{ scopeLabel(row.scope) }}
          </div>
        </div>
        <el-tag size="small" :type="isEnabled(row) ? 'success' : 'danger'" effect="plain">
          {{ isEnabled(row) ? '启用' : '停用' }}
        </el-tag>
      </div>
      <div class="meter">
        <span>延迟</span>
        <div class="track"><i :style="{ width: latencyWidth(row) }" /></div>
        <b class="numeric">{{ latencyText(row) }}</b>
      </div>
      <div class="meter">
        <span>配额</span>
        <div class="track"><i class="quota" :style="{ width: quotaWidth(row) }" /></div>
        <b class="numeric">{{ quotaText(row) }}</b>
      </div>
      <div class="card-acts">
        <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
        <el-button link type="primary" :disabled="isDefaultChat(row)" @click="setDefault(row)">
          {{ isDefaultChat(row) ? '默认 · chat' : '设为默认' }}
        </el-button>
        <el-button link type="primary" :loading="probing === rowKey(row)" @click="probeOne(row)">健康探测</el-button>
      </div>
    </article>

    <el-dialog v-model="dlg" :title="form.modelId ? '编辑模型' : '添加模型'" width="520px">
      <el-form label-width="88px">
        <el-form-item label="名称"><el-input v-model="form.modelName" placeholder="Grok-4 Fast" /></el-form-item>
        <el-form-item label="编码"><el-input v-model="form.modelCode" placeholder="grok-4-fast" :disabled="Boolean(form.modelId)" /></el-form-item>
        <el-form-item label="厂商"><el-input v-model="form.provider" placeholder="xAI / OpenAI" /></el-form-item>
        <el-form-item label="范围">
          <el-select v-model="form.scope" style="width:100%">
            <el-option label="AI 助手 (chat)" value="chat" />
            <el-option label="全局 (global)" value="global" />
            <el-option label="行情 (market)" value="market" />
            <el-option label="舆情 (sentiment)" value="sentiment" />
            <el-option label="量化 (quant)" value="quant" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.apiKey" type="password" show-password autocomplete="new-password" placeholder="**** 不回显明文" />
        </el-form-item>
        <el-form-item label="Base URL"><el-input v-model="form.baseUrl" placeholder="可选" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.status" active-value="0" inactive-value="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <template #legend>
      <span>tabular-nums · glass-panel · 密钥脱敏 · GET /ai/model/list</span>
    </template>
  </PageFrame>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import PageFrame from '@/components/page/PageFrame.vue'
import { addModel, getModel, listModel, listModelAll, updateModel } from '@/api/ai'
import { isMaskedSecret, maskSecret, sanitizePublicText } from '@/utils/secret'
import { unwrap, unwrapList } from '@/utils/list'
import { useUserStore } from '@/store/user'
import { errorText, isDemoSession, stubModels } from '@/utils/stubs'

const userStore = useUserStore()
function demoMode() {
  return isDemoSession(userStore)
}

const SCOPE = { global: 'global', sentiment: 'sentiment', chat: 'chat', market: 'market', quant: 'quant' }

const loading = ref(false)
const saving = ref(false)
const usingStub = ref(false)
const loadError = ref('')
const rows = ref([])
const dlg = ref(false)
const probing = ref('')
const probingAll = ref(false)
const lastPingAt = ref('')
const form = reactive(emptyForm())

function emptyForm() {
  return { modelId: undefined, modelName: '', modelCode: '', provider: '', scope: 'chat', apiKey: '', baseUrl: '', status: '0' }
}

function rowKey(row) {
  return String(row.modelId || row.modelCode || row.modelName)
}
function isEnabled(row) {
  return String(row.status ?? '0') === '0' || row.status === 0 || row.enabled === true
}
function scopeLabel(scope) {
  return SCOPE[scope] || scope || 'chat'
}
function latencyMs(row) {
  const n = Number(row.latencyMs ?? row.latency ?? row.avgLatency)
  return Number.isFinite(n) ? n : 0
}
function quotaPct(row) {
  const n = Number(row.quotaPct ?? row.quota ?? row.quotaUsed)
  if (!Number.isFinite(n)) return 0
  return n > 1 ? Math.min(100, n) : n * 100
}
function latencyText(row) {
  const n = latencyMs(row)
  return n ? `${Math.round(n)}ms` : '--'
}
function quotaText(row) {
  const n = quotaPct(row)
  return n ? `${Math.round(n)}%` : '--'
}
function latencyWidth(row) {
  const n = latencyMs(row)
  return `${Math.max(8, Math.min(100, n / 8))}%`
}
function quotaWidth(row) {
  return `${Math.max(0, Math.min(100, quotaPct(row)))}%`
}
function isDefaultChat(row) {
  if (row.isDefault || row.defaultChat) return true
  const chats = rows.value.filter((r) => (r.scope === 'chat' || r.scope === 'global') && isEnabled(r))
  return Boolean(chats[0] && rowKey(chats[0]) === rowKey(row) && (row.scope === 'chat' || row.scope === 'global'))
}

const kpis = computed(() => {
  const list = rows.value
  const enabled = list.filter(isEnabled).length
  const latencies = list.map(latencyMs).filter((n) => n > 0)
  const avg = latencies.length ? Math.round(latencies.reduce((s, n) => s + n, 0) / latencies.length) : 0
  const healthy = list.filter((r) => r.health !== 'down' && isEnabled(r)).length
  const def = list.find((r) => r.isDefault || r.defaultChat) || list.find((r) => r.scope === 'chat' && isEnabled(r))
  return {
    total: list.length,
    enabled,
    disabled: list.length - enabled,
    defaultName: def?.modelName || def?.modelCode || '--',
    avgLatency: avg ? `${avg}ms` : '--',
    healthText: healthy >= Math.max(1, enabled - 1) ? '正常' : '异常',
    healthCls: healthy >= Math.max(1, enabled - 1) ? 'up' : 'down',
    healthSub: lastPingAt.value ? `最近 ping ${lastPingAt.value}` : '待探测'
  }
})

function normalize(list) {
  return list.map((item) => ({
    ...item,
    modelName: item.modelName || item.name || item.modelCode,
    modelCode: item.modelCode || item.modelKey || item.code,
    provider: item.provider || item.vendor || '--',
    scope: item.scope || 'chat',
    status: item.status ?? '0',
    latencyMs: item.latencyMs ?? item.latency,
    quotaPct: item.quotaPct ?? item.quota,
    apiKey: undefined
  }))
}

function nowStamp() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function applyStub() {
  if (!demoMode()) return
  usingStub.value = true
  loadError.value = ''
  rows.value = stubModels()
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
    const [listRes, allRes] = await Promise.allSettled([
      listModel({ pageNum: 1, pageSize: 50 }),
      listModelAll()
    ])
    let list = []
    const errors = []
    if (listRes.status === 'fulfilled') list = unwrapList(listRes.value)
    else errors.push(errorText(listRes.reason, '模型列表加载失败'))
    if (!list.length && allRes.status === 'fulfilled') list = unwrapList(allRes.value)
    else if (allRes.status === 'rejected') errors.push(errorText(allRes.reason, '全部模型加载失败'))
    rows.value = normalize(list)
    if (!list.length && errors.length) loadError.value = errors.join('；')
  } catch (e) {
    rows.value = []
    loadError.value = errorText(e, '模型加载失败')
  } finally {
    loading.value = false
  }
}

function openAdd() {
  Object.assign(form, emptyForm())
  dlg.value = true
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    modelId: row.modelId,
    modelName: row.modelName,
    modelCode: row.modelCode,
    provider: row.provider,
    scope: row.scope || 'chat',
    apiKey: maskSecret(row.apiKeyMasked || '****'),
    baseUrl: row.baseUrl || '',
    status: isEnabled(row) ? '0' : '1'
  })
  dlg.value = true
}

async function save() {
  if (!form.modelName.trim() && !form.modelCode.trim()) {
    ElMessage.warning('请填写名称或编码')
    return
  }
  saving.value = true
  try {
    const payload = {
      modelId: form.modelId,
      modelName: form.modelName,
      modelCode: form.modelCode,
      provider: form.provider,
      scope: form.scope,
      baseUrl: form.baseUrl,
      status: form.status
    }
    if (!isMaskedSecret(form.apiKey)) payload.apiKey = form.apiKey
    if (form.modelId) await updateModel(payload)
    else await addModel(payload)
    ElMessage.success('已保存')
    dlg.value = false
    await load()
  } catch (e) {
    ElMessage.error(sanitizePublicText(e?.message, '保存失败'))
  } finally {
    saving.value = false
    form.apiKey = ''
  }
}

async function setDefault(row) {
  if (usingStub.value) {
    rows.value = rows.value.map((r) => ({ ...r, isDefault: rowKey(r) === rowKey(row) }))
    ElMessage.success('已设为默认（STUB）')
    return
  }
  try {
    await updateModel({ ...row, isDefault: true, defaultChat: true })
    ElMessage.success('已设为默认')
    await load()
  } catch (e) {
    ElMessage.error(sanitizePublicText(e?.message, '设置失败'))
  }
}

async function probeOne(row) {
  probing.value = rowKey(row)
  const t0 = performance.now()
  try {
    if (row.modelId && !usingStub.value) await getModel(row.modelId)
    const ms = Math.round(performance.now() - t0)
    row.latencyMs = ms
    row.health = 'ok'
    lastPingAt.value = nowStamp()
    ElMessage.success(`探测完成 ${ms}ms`)
  } catch {
    row.health = 'down'
    lastPingAt.value = nowStamp()
    ElMessage.warning('探测失败')
  } finally {
    probing.value = ''
  }
}

async function probeAll() {
  probingAll.value = true
  try {
    for (const row of rows.value) await probeOne(row)
  } finally {
    probingAll.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kpi-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.kpi-5 em { font-style: normal; }
.model-card {
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}
.card-top, .card-acts, .meter { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.card-top { align-items: flex-start; }
.meta { font-size: 12px; }
.meter span { width: 36px; color: var(--text-secondary); font-size: 12px; }
.meter b { width: 64px; text-align: right; font-size: 12px; }
.track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-muted);
  overflow: hidden;
}
.track i {
  display: block;
  height: 100%;
  background: color-mix(in srgb, var(--accent) 55%, transparent);
}
.track i.quota { background: color-mix(in srgb, var(--text-secondary) 45%, transparent); }
.muted { color: var(--text-secondary); font-size: 12px; }
@media (max-width: 1100px) { .kpi-5 { grid-template-columns: 1fr 1fr; } }
</style>
