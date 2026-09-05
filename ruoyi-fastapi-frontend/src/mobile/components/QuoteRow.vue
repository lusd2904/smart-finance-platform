<template>
  <button type="button" class="m-quote" @click="$emit('click')">
    <div class="m-quote__left">
      <div class="m-quote__name">
        <span v-if="rank != null" class="m-quote__rank">{{ rank }}</span>
        {{ name || symbol }}
        <span v-if="tag" class="m-quote__tag" :class="'is-' + tagTone">{{ tag }}</span>
        <span v-if="watched" class="m-quote__star" title="自选">★</span>
      </div>
      <div class="m-quote__sub">
        <span>{{ symbol }}</span>
        <span v-if="marketText"> · {{ marketText }}</span>
        <span v-if="subtitle"> · {{ subtitle }}</span>
      </div>
    </div>
    <div class="m-quote__right">
      <div class="m-quote__last m-num">{{ lastText }}</div>
      <div class="m-quote__chg m-num" :class="'m-' + tone">{{ chgText }}</div>
    </div>
  </button>
</template>

<script setup>
import { changeTone, fmtPct, fmtPrice, marketLabel } from '../utils/format'

const props = defineProps({
  symbol: { type: String, default: '' },
  name: { type: String, default: '' },
  market: { type: String, default: '' },
  last: { type: [Number, String], default: null },
  changePct: { type: [Number, String], default: null },
  rank: { type: [Number, String], default: null },
  inWatchlist: { type: Boolean, default: false },
  tag: { type: String, default: '' },
  tagTone: { type: String, default: 'flat' },
  subtitle: { type: String, default: '' }
})
defineEmits(['click'])

const lastText = computed(() => fmtPrice(props.last))
const chgText = computed(() => fmtPct(props.changePct))
const tone = computed(() => changeTone(props.changePct))
const marketText = computed(() => marketLabel(props.market))
const watched = computed(() => !!props.inWatchlist)
</script>

<style scoped lang="scss">
.m-quote {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border: 0;
  background: #fff;
  text-align: left;
  border-bottom: 1px solid #f0f1f3;
}
.m-quote__name {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
}
.m-quote__rank {
  display: inline-block;
  min-width: 18px;
  margin-right: 4px;
  color: #9ca3af;
  font-size: 12px;
  font-weight: 600;
}
.m-quote__sub {
  margin-top: 2px;
  color: #8b8d98;
  font-size: 11px;
}
.m-quote__right {
  text-align: right;
}
.m-quote__last {
  font-size: 16px;
  font-weight: 700;
}
.m-quote__chg {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 600;
}
.m-quote__tag {
  margin-left: 6px;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  background: #f3f4f6;
  color: #6b7280;
  vertical-align: middle;
}
.m-quote__tag.is-up { background: rgba(229, 72, 77, 0.12); color: #e5484d; }
.m-quote__tag.is-down { background: rgba(48, 164, 108, 0.12); color: #30a46c; }
.m-quote__star {
  margin-left: 4px;
  color: #f5a524;
  font-size: 11px;
}
</style>
