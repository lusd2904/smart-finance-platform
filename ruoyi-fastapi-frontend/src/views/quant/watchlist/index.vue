<template>
  <div class="app-container quant-watchlist">
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['quant:watchlist:add']">新增自选</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="danger" plain icon="Delete" :disabled="ids.length === 0" @click="handleDelete()" v-hasPermi="['quant:watchlist:remove']">批量删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button icon="Refresh" @click="getList">刷新</el-button>
      </el-col>
    </el-row>

    <el-table v-loading="loading" :data="watchList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="编号" prop="id" width="80" align="center" />
      <el-table-column label="代码" prop="symbol" width="140" />
      <el-table-column label="名称" prop="name">
        <template #default="scope">{{ symbolName(scope.row.symbol, scope.row.market) }}</template>
      </el-table-column>
      <el-table-column label="市场" prop="market" width="100" align="center">
        <template #default="scope">{{ marketLabel(scope.row.market) }}</template>
      </el-table-column>
      <el-table-column label="备注" prop="note" :show-overflow-tooltip="true" />
      <el-table-column label="添加时间" prop="createTime" width="180" align="center">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" @click="openSymbol(scope.row)">详情</el-button>
          <el-button link type="success" @click="openScan(scope.row)">扫描结果</el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['quant:watchlist:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 新增对话框 -->
    <el-dialog title="新增自选" v-model="open" width="500px" append-to-body>
      <el-form ref="watchRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="标的" prop="symbolKey">
          <el-select v-model="form.symbolKey" placeholder="选择标的" filterable style="width: 100%" @change="onSymbolChange">
            <el-option v-for="it in instruments" :key="it.symbol + it.market" :label="`${it.name} (${it.symbol})`" :value="it.symbol + '|' + it.market" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="3" placeholder="请输入备注（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="submitLoading" @click="submitForm">确 定</el-button>
        <el-button @click="open = false">取 消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="QuantWatchlist">
import { listWatchlist, addWatchlist, delWatchlist } from '@/api/quant';
import { listInstrument } from '@/api/market';

const { proxy } = getCurrentInstance();

const watchList = ref([]);
const loading = ref(false);
const total = ref(0);
const ids = ref([]);
const open = ref(false);
const submitLoading = ref(false);
const instruments = ref([]);

const queryParams = ref({ pageNum: 1, pageSize: 10 });

const form = ref({ symbolKey: '', symbol: '', market: '', note: '' });
const rules = {
  symbolKey: [{ required: true, message: '请选择标的', trigger: 'change' }]
};

const router = useRouter();

function marketLabel(market) {
  const m = { us: '美股', hk: '港股', a: 'A股', cn: 'A股' };
  return m[String(market).toLowerCase()] || market || '';
}

function openSymbol(row) {
  router.push({ path: '/market/symbol', query: { symbol: row.symbol, market: row.market || 'US' } });
}

function openScan(row) {
  router.push({ path: '/quant/scan-result', query: { symbol: row.symbol, market: row.market || 'US' } });
}

function symbolName(symbol, market) {
  const hit = instruments.value.find(it => it.symbol === symbol && (!market || it.market === market));
  return (hit && hit.name) || symbol || '--';
}

function loadInstruments() {
  listInstrument().then(response => {
    instruments.value = response.data || response.rows || [];
  });
}

/** 查询列表 */
function getList() {
  loading.value = true;
  listWatchlist(queryParams.value).then(response => {
    watchList.value = response.rows || response.data || [];
    total.value = response.total || watchList.value.length;
    loading.value = false;
  }).catch(() => {
    loading.value = false;
  });
}

function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.id);
}

function onSymbolChange(val) {
  if (val) {
    const [symbol, market] = val.split('|');
    form.value.symbol = symbol;
    form.value.market = market;
  }
}

/** 新增 */
function handleAdd() {
  form.value = { symbolKey: '', symbol: '', market: '', note: '' };
  open.value = true;
  nextTick(() => proxy.$refs['watchRef'] && proxy.$refs['watchRef'].clearValidate());
}

function submitForm() {
  proxy.$refs['watchRef'].validate(valid => {
    if (valid) {
      submitLoading.value = true;
      addWatchlist({ symbol: form.value.symbol, market: form.value.market, note: form.value.note }).then(() => {
        proxy.$modal.msgSuccess('新增成功');
        open.value = false;
        getList();
      }).finally(() => {
        submitLoading.value = false;
      });
    }
  });
}

/** 删除 */
function handleDelete(row) {
  const delIds = row ? row.id : ids.value.join(',');
  proxy.$modal.confirm('是否确认删除选中的自选标的?').then(() => {
    return delWatchlist(delIds);
  }).then(() => {
    proxy.$modal.msgSuccess('删除成功');
    getList();
  }).catch(() => {});
}

onMounted(() => {
  loadInstruments();
  getList();
});
</script>

<style lang="scss" scoped>
.quant-watchlist {
  .mb8 { margin-bottom: 8px; }
}
</style>
