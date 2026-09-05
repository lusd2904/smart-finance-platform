<template>
  <Teleport to="body">
    <div v-if="modelValue" class="m-drawer-mask" @click="close">
      <div class="m-drawer" @click.stop>
        <div class="m-drawer__title">交易 {{ symbol }}{{ name ? ' · ' + name : '' }}</div>
        <div class="m-side">
          <button type="button" :class="{ 'is-on': side === 'buy', 'is-buy': true }" @click="side = 'buy'">买入</button>
          <button type="button" :class="{ 'is-on': side === 'sell', 'is-sell': true }" @click="side = 'sell'">卖出</button>
        </div>
        <label class="m-field">
          <span>限价</span>
          <input v-model="priceText" inputmode="decimal" placeholder="价格" />
        </label>
        <label class="m-field">
          <span>数量</span>
          <input v-model="qtyText" inputmode="numeric" placeholder="股数" />
        </label>
        <div class="m-pct">
          <button v-for="p in [25, 50, 75, 100]" :key="p" type="button" @click="applyPercent(p)">
            {{ p === 100 ? '全仓' : p + '%' }}
          </button>
        </div>
        <p v-if="hint" class="m-drawer__hint">{{ hint }}</p>
        <button type="button" class="m-drawer__submit" :class="'is-' + side" :disabled="busy" @click="confirmSubmit">
          {{ busy ? '提交中…' : (side === 'sell' ? '卖出' : '买入') }}
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { getTradeAccount, getTradePositions, submitTradeOrder } from '@/api/trade'
import { unwrapData, unwrapList, num } from '../utils/payload'
import { cashCurrencyForMarket, inferMarket, quoteSymbol, ticketQtyForPercent } from '../utils/ticketQty'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  symbol: { type: String, default: '' },
  market: { type: String, default: 'US' },
  name: { type: String, default: '' },
  last: { type: [Number, String], default: null },
  side: { type: String, default: 'buy' }
})
const emit = defineEmits(['update:modelValue', 'done'])

const side = ref(props.side === 'sell' ? 'sell' : 'buy')
const priceText = ref('')
const qtyText = ref('')
const hint = ref('')
const busy = ref(false)
const account = ref(null)
const positions = ref([])

watch(() => props.modelValue, (open) => {
  if (!open) return
  side.value = props.side === 'sell' ? 'sell' : 'buy'
  priceText.value = props.last != null && Number(props.last) > 0 ? String(props.last) : ''
  qtyText.value = ''
  hint.value = ''
  loadBook()
})
watch(() => props.side, (v) => {
  if (props.modelValue) side.value = v === 'sell' ? 'sell' : 'buy'
})

const refPrice = computed(() => {
  const typed = num(priceText.value)
  if (typed != null && typed > 0) return typed
  return num(props.last)
})

function cashOf() {
  const acc = account.value
  if (!acc) return null
  const ccy = cashCurrencyForMarket(props.market)
  const bals = Array.isArray(acc.balances) ? acc.balances : []
  const hit = bals.find((b) => String(b.currency || '').toUpperCase() === ccy)
  if (hit) return num(hit.availableCash ?? hit.totalCash)
  if (String(acc.currency || '').toUpperCase() === ccy) return num(acc.availableCash ?? acc.totalCash)
  return null
}

function sellableOf() {
  const code = quoteSymbol(props.symbol).toUpperCase()
  const full = String(props.symbol || '').toUpperCase()
  for (const p of positions.value) {
    const s = String(p.symbol || '').toUpperCase()
    if (s === full || quoteSymbol(s).toUpperCase() === code) {
      return num(p.availableQuantity ?? p.quantity)
    }
  }
  return null
}

async function loadBook() {
  try {
    const [accRes, posRes] = await Promise.all([
      getTradeAccount().catch(() => null),
      getTradePositions().catch(() => null)
    ])
    account.value = accRes ? unwrapData(accRes) : null
    positions.value = posRes ? unwrapList(posRes, ['positions', 'items', 'rows']) : []
    refreshHint()
  } catch {
    hint.value = '账户信息暂不可用'
  }
}

function refreshHint() {
  const maxQty = ticketQtyForPercent({
    percent: 100,
    side: side.value,
    market: props.market || inferMarket(props.symbol),
    price: refPrice.value,
    cash: cashOf(),
    sellable: sellableOf()
  })
  if (side.value === 'sell') {
    hint.value = maxQty > 0 ? `可卖 ${maxQty} 股` : '无可卖仓位'
    return
  }
  if (refPrice.value == null) {
    hint.value = '缺少价格，数量按 0 处理，请先填写限价'
    return
  }
  hint.value = maxQty > 0 ? `可买 ${maxQty} 股` : '购买力不足或缺少价格，数量为 0'
}

function applyPercent(percent) {
  const n = ticketQtyForPercent({
    percent,
    side: side.value,
    market: props.market || inferMarket(props.symbol),
    price: refPrice.value,
    cash: cashOf(),
    sellable: sellableOf()
  })
  if (n <= 0) {
    hint.value = side.value === 'sell' ? '无可卖仓位' : '购买力不足或缺少价格'
    qtyText.value = '0'
    return
  }
  qtyText.value = String(n)
  refreshHint()
}

watch([side, priceText], refreshHint)

function close() {
  emit('update:modelValue', false)
}

async function confirmSubmit() {
  const qty = Math.floor(num(qtyText.value) || 0)
  const px = num(priceText.value)
  if (qty <= 0) {
    hint.value = '请输入股数（缺少价格或购买力时数量为 0）'
    return
  }
  if (px == null || px <= 0) {
    hint.value = '限价单请填写有效价格'
    return
  }
  const ok = window.confirm(`确认${side.value === 'sell' ? '卖出' : '买入'} ${props.symbol} ${qty} 股 @ ${px}？`)
  if (!ok) return
  busy.value = true
  try {
    const res = await submitTradeOrder({
      symbol: props.symbol,
      market: props.market || inferMarket(props.symbol),
      side: side.value,
      orderType: 'LO',
      quantity: qty,
      price: px
    })
    const data = unwrapData(res)
    const success = data.ok === true || data.orderId != null || res.code === 200
    hint.value = data.message || res.msg || (success ? '已提交委托' : '下单失败')
    if (success) {
      emit('done', data)
      close()
    }
  } catch (e) {
    hint.value = (e && e.message) || '下单失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped lang="scss">
.m-drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(17, 24, 39, 0.45);
  display: flex;
  align-items: flex-end;
}
.m-drawer {
  width: 100%;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom, 0px));
  background: #fff;
  border-radius: 16px 16px 0 0;
}
.m-drawer__title {
  font-size: 16px;
  font-weight: 800;
  margin-bottom: 12px;
}
.m-side {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.m-side button {
  flex: 1;
  height: 36px;
  border: 0;
  border-radius: 8px;
  background: #f3f4f6;
  color: #6b7280;
  font-weight: 700;
}
.m-side button.is-on.is-buy { background: #e5484d; color: #fff; }
.m-side button.is-on.is-sell { background: #30a46c; color: #fff; }
.m-field {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  color: #6b7280;
}
.m-field input {
  flex: 1;
  height: 40px;
  padding: 0 10px;
  border: 1px solid #ececef;
  border-radius: 8px;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
.m-pct {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.m-pct button {
  flex: 1;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: #f3f4f6;
  font-size: 12px;
  font-weight: 600;
}
.m-drawer__hint {
  margin: 0 0 10px;
  color: #6b7280;
  font-size: 12px;
}
.m-drawer__submit {
  width: 100%;
  height: 44px;
  border: 0;
  border-radius: 10px;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
}
.m-drawer__submit.is-buy { background: #e5484d; }
.m-drawer__submit.is-sell { background: #30a46c; }
.m-drawer__submit:disabled { opacity: 0.6; }
</style>
