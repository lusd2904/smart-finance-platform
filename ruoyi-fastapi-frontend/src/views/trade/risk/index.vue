<template>
  <div class="app-container">
    <div class="page-hero">
      <div><h2>风控管理</h2><p>规则配置 · 扫描 · 事件</p></div>
      <div>
        <el-button type="warning" :loading="scanning" @click="scan">执行扫描</el-button>
        <el-button type="primary" @click="openRule()">新增规则</el-button>
      </div>
    </div>
    <el-row :gutter="16">
      <el-col :md="12" :xs="24">
        <el-card shadow="never"><template #header>风控规则</template>
          <el-table :data="rules" v-loading="loading" size="small">
            <el-table-column prop="ruleName" label="名称" min-width="120"/>
            <el-table-column prop="ruleType" label="类型" width="110"/>
            <el-table-column prop="threshold" label="阈值" width="80"/>
            <el-table-column prop="enabled" label="启用" width="70">
              <template #default="{row}"><el-tag size="small" :type="row.enabled==='1'?'success':'info'">{{ row.enabled==='1'?'是':'否' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{row}">
                <el-button link type="primary" @click="openRule(row)">编辑</el-button>
                <el-button link type="danger" @click="remove(row)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :md="12" :xs="24">
        <el-card shadow="never"><template #header>风险事件</template>
          <el-table :data="events" size="small" max-height="420">
            <el-table-column prop="createTime" label="时间" width="160"/>
            <el-table-column prop="eventLevel" label="级别" width="80">
              <template #default="{row}"><el-tag size="small" :type="row.eventLevel==='danger'?'danger':'warning'">{{ row.eventLevel||'warn' }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="symbol" label="标的" width="90"/>
            <el-table-column prop="title" label="标题" min-width="140"/>
            <el-table-column prop="content" label="内容" min-width="180" show-overflow-tooltip/>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
    <el-dialog v-model="dlg" title="风控规则" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.ruleName"/></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.ruleType" style="width:100%">
            <el-option label="仓位 position" value="position"/>
            <el-option label="亏损 loss" value="loss"/>
            <el-option label="集中度 concentration" value="concentration"/>
          </el-select>
        </el-form-item>
        <el-form-item label="阈值"><el-input-number v-model="form.threshold" :min="0" :max="100" style="width:100%"/></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" active-value="1" inactive-value="0"/></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup name="TradeRisk">
import { listRiskRules, saveRiskRule, deleteRiskRule, listRiskEvents, evaluateRisk } from '@/api/trade'
const {proxy}=getCurrentInstance()
const loading=ref(false); const scanning=ref(false); const rules=ref([]); const events=ref([])
const dlg=ref(false); const form=ref({})
async function load(){
  loading.value=true
  try{ const [r,e]=await Promise.all([listRiskRules(), listRiskEvents(50)]); rules.value=r.data||[]; events.value=e.data||[] }
  finally{ loading.value=false }
}
function openRule(row){ form.value=row?{...row}:{ruleName:'', ruleType:'position', threshold:20, enabled:'1', remark:''}; dlg.value=true }
async function save(){ await saveRiskRule(form.value); proxy.$modal.msgSuccess('已保存'); dlg.value=false; load() }
async function remove(row){ await proxy.$modal.confirm('删除规则？'); await deleteRiskRule(row.ruleId); load() }
async function scan(){ scanning.value=true; try{ const res=await evaluateRisk(); proxy.$modal.msgSuccess(res.msg||'完成'); load() } finally{ scanning.value=false } }
onMounted(load)
</script>
<style scoped>
.page-hero{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.page-hero h2{margin:0 0 4px;color:var(--text-emphasis)} .page-hero p{margin:0;color:var(--text-muted);font-size:13px}
</style>
