<template>
  <div class="app-container">
    <el-alert
      title="只作用于需求沟通。勾选已配置的 AI，并指定唯一清单确定者。未配置时群里仍默认 Grok。"
      type="info"
      show-icon
      :closable="false"
      class="mb16"
    />
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" icon="Plus" @click="addRow" v-hasPermi="['ai:req:bot:edit']">添加机器人</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" :loading="saving" @click="handleSave" v-hasPermi="['ai:req:bot:edit']">保存</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button icon="Refresh" @click="load">刷新</el-button>
      </el-col>
    </el-row>
    <el-table v-loading="loading" :data="bots">
      <el-table-column label="参与" width="80" align="center">
        <template #default="scope">
          <el-switch v-model="scope.row.enabled" />
        </template>
      </el-table-column>
      <el-table-column label="已配置 AI" min-width="220">
        <template #default="scope">
          <el-select v-model="scope.row.modelId" filterable placeholder="选择模型" style="width: 100%">
            <el-option
              v-for="m in models"
              :key="m.modelId"
              :label="`${m.modelName || m.modelCode} (${m.provider})`"
              :value="m.modelId"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="群内显示名" width="180">
        <template #default="scope">
          <el-input v-model="scope.row.displayName" maxlength="64" />
        </template>
      </el-table-column>
      <el-table-column label="清单确定者" width="120" align="center">
        <template #default="scope">
          <el-radio
            :model-value="deciderKey"
            :label="scope.row._key"
            @change="setDecider(scope.row)"
          >确定者</el-radio>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="scope">
          <el-button link type="danger" @click="removeRow(scope.$index)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!bots.length && !loading" description="未配置则需求沟通仍使用默认 Grok" />
  </div>
</template>

<script setup name="AiReqBotIndex">
import { listReqBots, saveReqBots } from '@/api/ai/req'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const saving = ref(false)
const bots = ref([])
const models = ref([])
let seq = 1

const deciderKey = computed(() => {
  const hit = bots.value.find(b => b.isDecider && b.enabled)
  return hit ? hit._key : ''
})

function addRow() {
  bots.value.push({
    _key: 'new-' + seq++,
    botId: null,
    modelId: models.value[0] && models.value[0].modelId,
    displayName: '',
    enabled: true,
    isDecider: bots.value.length === 0
  })
}

function removeRow(index) {
  bots.value.splice(index, 1)
}

function setDecider(row) {
  bots.value.forEach(item => {
    item.isDecider = item._key === row._key
  })
}

async function load() {
  loading.value = true
  try {
    const res = await listReqBots()
    const data = res.data || {}
    models.value = data.models || []
    bots.value = (data.bots || []).map(b => ({
      _key: 'bot-' + (b.botId || seq++),
      botId: b.botId,
      modelId: b.modelId,
      displayName: b.displayName,
      enabled: !!b.enabled,
      isDecider: !!b.isDecider
    }))
  } finally {
    loading.value = false
  }
}

function handleSave() {
  const enabled = bots.value.filter(b => b.enabled)
  const deciders = enabled.filter(b => b.isDecider)
  if (enabled.length && deciders.length !== 1) {
    proxy.$modal.msgError('必须在已勾选成员中指定唯一确定者')
    return
  }
  saving.value = true
  saveReqBots({
    bots: bots.value.map((b, index) => ({
      modelId: b.modelId,
      displayName: b.displayName,
      enabled: b.enabled,
      isDecider: b.isDecider,
      sortOrder: index
    }))
  })
    .then(() => {
      proxy.$modal.msgSuccess('已保存，下一轮讨论生效')
      load()
    })
    .finally(() => {
      saving.value = false
    })
}

onMounted(load)
</script>

<style scoped>
.mb16 { margin-bottom: 16px; }
.mb8 { margin-bottom: 8px; }
</style>
