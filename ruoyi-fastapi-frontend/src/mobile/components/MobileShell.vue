<template>
  <div class="m-app" :class="{ 'm-app--tabs': showTabs }">
    <div class="m-app__body">
      <router-view v-slot="{ Component }">
        <keep-alive :include="kept">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </div>
    <MobileTabBar v-if="showTabs" />
  </div>
</template>

<script setup>
import MobileTabBar from './MobileTabBar.vue'
import '../styles/mobile.scss'

const kept = ['MobileHeat', 'MobileSentiment', 'MobilePicks', 'MobilePositions', 'MobileMe']
const route = useRoute()
const showTabs = computed(() => !route.meta.hideTab)
</script>
