<template>
  <div class="app-container trading-desk">
    <div class="page-hero">
      <div>
        <h2>交易台</h2>
        <p>账户 · 报价 · 持仓 · 下单 · 委托（长桥）</p>
      </div>
      <div class="acts">
        <el-button @click="$router.push('/quant/longbridge')">长桥配置</el-button>
        <el-button @click="$router.push('/trade/risk')">风控</el-button>
        <el-button type="primary" :loading="loading" icon="Refresh" @click="refreshAll">刷新全部</el-button>
      </div>
    </div>
    <el-alert
      v-if="!configured"
      type="warning"
      show-icon
      class="mb12"
      title="长桥未配置或未连通：可浏览页面，真实下单/持仓需先配置凭证"
    />
    <el-row :gutter="12">
      <el-col :lg="6" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>快速报价</template>
          <el-input v-model="form.symbol" placeholder="代码" class="mb8" @keyup.enter="loadQuote">
            <template #append><el-button @click="loadQuote">查价</el-button></template>
          </el-input>
          <div v-if="quote.price" class="quote-box">
            <div class="q-sym">{{ form.symbol }} <span class="muted">{{ form.market }}</span></div>
            <div class="q-price" :class="quote.up ? 'up' : 'down'">{{ quote.price }}</div>
            <div class="q-chg" :class="quote.up ? 'up' : 'down'">{{ quote.changeText }}</div>
            <div class="q-meta">O {{ quote.open }} · H {{ quote.high }} · L {{ quote.low }} · V {{ quote.volume || '--' }}</div>
          </div>
          <el-empty v-else description="输入代码查询近价" :image-size="60" />
        </el-card>
        <el-card shadow="never">
          <template #header>资金</template>
          <el-table :data="account.balances || []" size="small" empty-text="暂无">
            <el-table-column prop="currency" label="币种" width="70" />
            <el-table-column prop="netAssets" label="净资产" />
            <el-table-column prop="availableCash" label="可用" />
            <el-table-column prop="buyPower" label="购买力" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :lg="8" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>下单面板</template>
          <el-form label-width="72px">
            <el-form-item label="市场">
              <el-select v-model="form.market" style="width: 100%" @change="loadQuote">
                <el-option label="US" value="US" />
                <el-option label="HK" value="HK" />
                <el-option label="CN" value="CN" />
              </el-select>
            </el-form-item>
            <el-form-item label="代码"><el-input v-model="form.symbol" @change="loadQuote" /></el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="form.side">
                <el-radio-button label="buy">买入</el-radio-button>
                <el-radio-button label="sell">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="form.orderType" style="width: 100%">
                <el-option label="限价 LO" value="LO" />
                <el-option label="市价 MO" value="MO" />
              </el-select>
            </el-form-item>
            <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" style="width: 100%" /></el-form-item>
            <el-form-item v-if="form.orderType === 'LO'" label="价格">
              <el-input-number v-model="form.price" :min="0.01" :step="0.01" style="width: 100%" />
              <el-button link type="primary" @click="form.price = Number(quote.price || form.price)">用现价</el-button>
            </el-form-item>
            <el-form-item label="预估">
              <span class="muted">名义金额 ≈ {{ notional }} · 可用 {{ availableCashText }}</span>
            </el-form-item>
            <el-button type="primary" style="width: 100%" :loading="submitting" :disabled="!configured" @click="submit">
              提交订单
            </el-button>
          </el-form>
        </el-card>
      </el-col>
      <el-col :lg="10" :xs="24">
        <el-card shadow="never" class="mb12">
          <template #header>
            <div class="hdr">
              <span>持仓快照</span>
              <el-button link type="primary" @click="$router.push('/trade/positions')">全部</el-button>
            </div>
          </template>
          <el-table :data="positions" size="small" max-height="220" empty-text="暂无持仓">
            <el-table-column prop="symbol" label="代码" width="90" />
            <el-table-column prop="quantity" label="数量" width="70" />
            <el-table-column prop="costPrice" label="成本" width="80" />
            <el-table-column prop="marketValue" label="市值" width="90" />
            <el-table-column label="操作" width="70">
              <template #default="{ row }"><el-button link type="primary" @click="fillFromPos(row)">填入</el-button></template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card shadow="never">
          <template #header>
            <div class="hdr">
              <span>委托</span>
              <div>
                <el-radio-group v-model="orderScope" size="small" @change="loadOrders">
                  <el-radio-button label="today">今日</el-radio-button>
                  <el-radio-button label="history">历史</el-radio-button>
                </el-radio-group>
                <el-button link type="primary" class="ml8" @click="$router.push('/trade/orders')">全部</el-button>
              </div>
            </div>
          </template>
          <el-table v-loading="loading" :data="orders" size="small" max-height="260">
            <el-table-column prop="symbol" label="标的" width="90" />
            <el-table-column prop="side" label="方向" width="70" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="quantity" label="量" width="70" />
            <el-table-column prop="price" label="价" width="80" />
            <el-table-column label="操作" width="70">
              <template #default="{ row }">
                <el-button v-if="row.orderId && orderScope === 'today'" link type="danger" @click="cancel(row)">撤</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script setup name="TradeTrading">
import { getTradeAccount, getTradeOrders, getTradePositions, submitTradeOrder, cancelTradeOrder } from '@/api/trade'
import { getKline } from '@/api/market'
const route = useRoute()
const { proxy } = getCurrentInstance()
const loading = ref(false)
const submitting = ref(false)
const account = ref({ balances: [] })
const orders = ref([])
const positions = ref([])
const configured = ref(true)
const orderScope = ref('today')
const form = ref({
  symbol: route.query.symbol || 'AAPL',
  market: route.query.market || 'US',
  side: 'buy',
  orderType: 'LO',
  quantity: 1,
  price: 100
})
const quote = ref({})
const notional = computed(() => {
  const p = form.value.orderType === 'MO' ? Number(quote.value.price || 0) : Number(form.value.price || 0)
  return (p * Number(form.value.quantity || 0)).toFixed(2)
})
const availableCashText = computed(() => {
  const b = (account.value.balances || [])[0]
  return b ? `${b.availableCash || '--'} ${b.currency || ''}` : '--'
})
function fillFromPos(row) {
  form.value.symbol = row.symbol
  form.value.side = 'sell'
  if (row.quantity) form.value.quantity = Number(row.quantity) || form.value.quantity
  loadQuote()
}
async function loadQuote() {
  try {
    const res = await getKline({ symbol: form.value.symbol, market: form.value.market, start: '-10d', stop: 'now()' })
    const kl = (res.data && res.data.klines) || []
    if (!kl.length) {
      quote.value = {}
      return
    }
    const last = kl[kl.length - 1]
    const prev = kl.length > 1 ? kl[kl.length - 2] : null
    const price = Number(last.close)
    let ch = null
    if (prev && prev.close) ch = ((price - Number(prev.close)) / Number(prev.close)) * 100
    quote.value = {
      price: price.toFixed(2),
      open: last.open,
      high: last.high,
      low: last.low,
      volume: last.volume,
      up: ch == null ? true : ch >= 0,
      changeText: ch == null ? '--' : `${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%`
    }
    if (form.value.orderType === 'LO' && !form.value.price) form.value.price = price
  } catch (e) {
    quote.value = {}
  }
}
async function loadOrders() {
  const o = await getTradeOrders(orderScope.value)
  orders.value = (o.data && o.data.orders) || []
  if (o.data && o.data.configured === false) configured.value = false
}
async function refreshAll() {
  loading.value = true
  try {
    const [a, p] = await Promise.all([getTradeAccount(), getTradePositions()])
    account.value = a.data || { balances: [] }
    configured.value = account.value.configured !== false
    positions.value = (p.data && p.data.positions) || []
    await loadOrders()
    await loadQuote()
  } finally {
    loading.value = false
  }
}
async function submit() {
  if (!form.value.symbol || !form.value.quantity) return proxy.$modal.msgError('请填写代码和数量')
  await proxy.$modal.confirm(`确认${form.value.side === 'buy' ? '买入' : '卖出'} ${form.value.symbol} x ${form.value.quantity}？`)
  submitting.value = true
  try {
    const res = await submitTradeOrder(form.value)
    const d = res.data || {}
    d.ok ? proxy.$modal.msgSuccess(d.message || '已提交') : proxy.$modal.msgError(d.message || '失败')
    await refreshAll()
  } finally {
    submitting.value = false
  }
}
async function cancel(row) {
  await proxy.$modal.confirm('撤单 ' + row.orderId + '？')
  const res = await cancelTradeOrder(row.orderId)
  const d = res.data || {}
  d.ok ? proxy.$modal.msgSuccess(d.message || '已撤') : proxy.$modal.msgError(d.message || '失败')
  await refreshAll()
}
onMounted(refreshAll)
</script>
<style scoped>
.page-hero { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.page-hero h2 { margin: 0 0 4px; color: var(--text-emphasis); }
.page-hero p { margin: 0; color: var(--text-muted); font-size: 13px; }
.acts { display: flex; gap: 8px; flex-wrap: wrap; }
.mb12 { margin-bottom: 12px; }
.mb8 { margin-bottom: 8px; }
.ml8 { margin-left: 8px; }
.quote-box { text-align: center; padding: 8px 0; }
.q-sym { font-weight: 700; color: var(--text-emphasis); }
.muted { color: var(--text-muted); font-size: 12px; }
.q-price { font-size: 32px; font-weight: 800; margin: 6px 0; }
.up { color: var(--stat-up, #f87171); }
.down { color: var(--stat-down, #34d399); }
.q-meta { font-size: 12px; color: var(--text-muted); }
.hdr { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
</style>
