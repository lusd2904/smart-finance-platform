<template>
  <div class="layout">
    <CyberBackground />
    <div class="shell-grid" aria-hidden="true"></div>
    <Sidebar />
    <div class="main-content">
      <Header />
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import CyberBackground from './CyberBackground.vue'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'
</script>

<style scoped lang="scss">
.layout {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  position: relative;
  background: transparent;
}

.shell-grid {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    var(--page-grid),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.028) 1px, transparent 1px);
  background-size: auto, 88px 88px, 88px 88px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.18), transparent 72%);
  opacity: 0.12;
}

.main-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  height: 100vh;
  overflow: hidden;
}

.content {
  position: relative;
  flex: 1;
  min-height: 0;
  padding: 16px 18px 20px;
  overflow: auto;
}
</style>
