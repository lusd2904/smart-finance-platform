<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="m-ticket"
      @touchstart.passive="onSwipeStart"
      @touchend="onSwipeEnd"
    >
        <header class="m-ticket__bar">
          <button type="button" class="m-ticket__back" @click="close">‹</button>
          <div class="m-ticket__title">交易 {{ symbol }}{{ name ? ' · ' + name : '' }}</div>
        </header>
        <div class="m-ticket__body" :style="{ paddingBottom: liftPad }">
        <template v-if="!confirming">
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
          <div class="m-field m-field--estimate">
            <span>预估金额</span>
            <strong class="m-num">{{ estimate }}</strong>
          </div>
          <div class="m-pct">
            <button v-for="p in [25, 50, 75, 100]" :key="p" type="button" @click="applyPercent(p)">
              {{ p === 100 ? '全仓' : p + '%' }}
            </button>
          </div>
          <p v-if="hint" class="m-drawer__hint" :class="{ 'is-warn': hintWarn }">{{ hint }}</p>
          <button type="button" class="m-drawer__submit" :class="'is-' + side" :disabled="busy" @click="openConfirm">
            {{ side === 'sell' ? '卖出' : '买入' }}
          </button>
        </template>
        <template v-else>
          <dl class="m-confirm-list">
            <div class="m-confirm-row">
              <dt>方向</dt>
              <dd>{{ side === 'sell' ? '卖出' : '买入' }}</dd>
            </div>
            <div class="m-confirm-row">
              <dt>代码</dt>
              <dd>{{ symbol }}</dd>
            </div>
            <div class="m-confirm-row">
              <dt>限价</dt>
              <dd class="m-num">{{ priceText }}</dd>
            </div>
            <div class="m-confirm-row">
              <dt>数量</dt>
              <dd class="m-num">{{ qtyText }}</dd>
            </div>
            <div class="m-confirm-row">
              <dt>预估金额</dt>
              <dd class="m-num">{{ estimate }}</dd>
            </div>
          </dl>
          <div class="m-confirm__btns">
            <button type="button" class="ghost" :disabled="busy" @click="confirming = false">取消</button>
            <button type="button" class="m-drawer__submit" :class="'is-' + side" :disabled="busy" @click="doSubmit">
              {{ busy ? '提交中…' : '确认提交' }}
            </button>
          </div>
        </template>
        <div v-if="toast" class="m-toast">{{ toast }}</div>
        </div>
    </div>
  </Teleport>
</template>

<script setup>
import { getTradeAccount, getTradePositions, submitTradeOrder } from '@/api/trade'
import { unwrapData, unwrapList, num } from '../utils/payload'
import { estimateNotional } from '../utils/format'
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
const hintWarn = ref(false)
const busy = ref(false)
const confirming = ref(false)
const toast = ref('')
const account = ref(null)
const positions = ref([])
const kbLift = ref(0)

const liftPad = computed(() => `calc(16px + env(safe-area-inset-bottom, 0px) + ${kbLift.value}px)`)
const estimate = computed(() => estimateNotional(priceText.value, qtyText.value))

watch(() => props.modelValue, (open) => {
  if (!open) {
    confirming.value = false
    return
  }
  side.value = props.side === 'sell' ? 'sell' : 'buy'
  priceText.value = props.last != null && Number(props.last) > 0 ? String(props.last) : ''
  qtyText.value = ''
  hint.value = ''
  hintWarn.value = false
  confirming.value = false
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
  let accFailed = false
  try {
    const [accRes, posRes] = await Promise.all([
      getTradeAccount().catch(() => {
        accFailed = true
        return null
      }),
      getTradePositions().catch(() => null)
    ])
    account.value = accRes ? unwrapData(accRes) : null
    positions.value = posRes ? unwrapList(posRes, ['positions', 'items', 'rows']) : []
    if (accFailed) {
      hint.value = '账户信息暂不可用'
      hintWarn.value = true
      return
    }
    refreshHint()
  } catch {
    hint.value = '账户信息暂不可用'
    hintWarn.value = true
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
    hintWarn.value = maxQty <= 0
    hint.value = maxQty > 0 ? `可卖 ${maxQty} 股` : '无可卖仓位'
    return
  }
  if (refPrice.value == null) {
    hintWarn.value = true
    hint.value = '缺少价格，数量按 0 处理，请先填写限价'
    return
  }
  hintWarn.value = maxQty <= 0
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
    hintWarn.value = true
    hint.value = side.value === 'sell' ? '无可卖仓位' : '购买力不足或缺少价格，数量为 0'
    qtyText.value = '0'
    return
  }
  qtyText.value = String(n)
  hintWarn.value = false
  refreshHint()
}

watch([side, priceText], refreshHint)

function close() {
  if (busy.value) return
  confirming.value = false
  emit('update:modelValue', false)
}

let swipeX = null
function onSwipeStart(e) {
  const x = e.touches && e.touches[0] ? e.touches[0].clientX : 0
  swipeX = x < 28 ? x : null
}
function onSwipeEnd(e) {
  if (swipeX == null) return
  const x = e.changedTouches && e.changedTouches[0] ? e.changedTouches[0].clientX : 0
  if (x - swipeX > 64) close()
  swipeX = null
}

function openConfirm() {
  const qty = Math.floor(num(qtyText.value) || 0)
  const px = num(priceText.value)
  if (qty <= 0) {
    hintWarn.value = true
    hint.value = '请输入股数（缺少价格或购买力时数量为 0）'
    return
  }
  if (px == null || px <= 0) {
    hintWarn.value = true
    hint.value = '限价单请填写有效价格'
    return
  }
  confirming.value = true
}

async function doSubmit() {
  if (busy.value) return
  const qty = Math.floor(num(qtyText.value) || 0)
  const px = num(priceText.value)
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
    if (success) {
      toast.value = data.message || res.msg || '已提交委托'
      emit('done', data)
      setTimeout(() => {
        toast.value = ''
        emit('update:modelValue', false)
      }, 700)
    } else {
      hintWarn.value = true
      hint.value = data.message || res.msg || '下单失败'
      confirming.value = false
    }
  } catch (e) {
    hintWarn.value = true
    hint.value = (e && e.message) || '下单失败'
    confirming.value = false
  } finally {
    busy.value = false
  }
}

function onViewport() {
  const vv = typeof window !== 'undefined' ? window.visualViewport : null
  if (!vv) {
    kbLift.value = 0
    return
  }
  kbLift.value = Math.max(0, window.innerHeight - vv.height - (vv.offsetTop || 0))
}

onMounted(() => {
  if (typeof window === 'undefined' || !window.visualViewport) return
  window.visualViewport.addEventListener('resize', onViewport)
  window.visualViewport.addEventListener('scroll', onViewport)
})
onBeforeUnmount(() => {
  if (typeof window === 'undefined' || !window.visualViewport) return
  window.visualViewport.removeEventListener('resize', onViewport)
  window.visualViewport.removeEventListener('scroll', onViewport)
})
</script>

<style scoped lang="scss">
.m-ticket {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: #fff;
  display: flex;
  flex-direction: column;
}
.m-ticket__bar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: calc(8px + env(safe-area-inset-top, 0px)) 8px 8px 4px;
  border-bottom: 1px solid #ececef;
}
.m-ticket__back {
  width: 40px;
  height: 40px;
  border: 0;
  background: transparent;
  font-size: 28px;
  line-height: 1;
}
.m-ticket__title {
  font-size: 16px;
  font-weight: 800;
}
.m-ticket__body {
  flex: 1;
  padding: 16px 16px 16px;
  overflow: auto;
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
.m-field--estimate {
  min-height: 40px;
}
.m-field--estimate strong {
  flex: 1;
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  text-align: right;
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
.m-drawer__hint.is-warn { color: #e5484d; }
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
.m-confirm-list {
  margin: 0 0 16px;
  padding: 0;
}
.m-confirm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 40px;
  padding: 6px 0;
  border-bottom: 1px solid #ececef;
  font-size: 14px;
}
.m-confirm-row dt {
  margin: 0;
  color: #6b7280;
  font-weight: 500;
}
.m-confirm-row dd {
  margin: 0;
  font-weight: 700;
  color: #111827;
  text-align: right;
}
.m-confirm__btns {
  display: flex;
  gap: 8px;
}
.m-confirm__btns .ghost {
  flex: 1;
  height: 44px;
  border: 1px solid #ececef;
  border-radius: 10px;
  background: #fff;
  font-weight: 700;
}
.m-confirm__btns .m-drawer__submit { flex: 2; }
</style>
