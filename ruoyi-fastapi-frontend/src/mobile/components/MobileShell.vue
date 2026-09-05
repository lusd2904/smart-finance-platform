<template>
  <div class="m-app" :class="{ 'm-app--tabs': isTab }">
    <div v-show="isTab" class="m-app__body">
      <Heat v-if="visited.heat" v-show="tab === 'heat'" />
      <Sentiment v-if="visited.sentiment" v-show="tab === 'sentiment'" />
      <Picks v-if="visited.picks" v-show="tab === 'picks'" />
      <Positions v-if="visited.positions" v-show="tab === 'positions'" />
      <Me v-if="visited.me" v-show="tab === 'me'" />
    </div>
    <div v-if="!isTab" class="m-app__body">
      <router-view />
    </div>
    <MobileTabBar v-if="isTab" />
  </div>
</template>

<script setup>
import MobileTabBar from './MobileTabBar.vue'
import Heat from '../views/Heat.vue'
import Sentiment from '../views/Sentiment.vue'
import Picks from '../views/Picks.vue'
import Positions from '../views/Positions.vue'
import Me from '../views/Me.vue'
import '../styles/mobile.scss'

const route = useRoute()
const tab = computed(() => route.meta.tab || '')
const isTab = computed(() => !!route.meta.tab && !route.meta.hideTab)
const visited = reactive({
  heat: false,
  sentiment: false,
  picks: false,
  positions: false,
  me: false
})

watch(tab, (key) => {
  if (key && Object.prototype.hasOwnProperty.call(visited, key)) {
    visited[key] = true
  }
}, { immediate: true })
</script>
