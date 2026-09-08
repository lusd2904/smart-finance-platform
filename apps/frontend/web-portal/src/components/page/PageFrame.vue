<template>
  <div class="sfp-page" v-loading="loading">
    <section class="hero-panel page-hero">
      <div class="hero-copy">
        <h2>{{ title }}</h2>
      </div>
      <div class="hero-actions">
        <slot name="actions" />
      </div>
    </section>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  loading: { type: Boolean, default: false }
})
</script>
