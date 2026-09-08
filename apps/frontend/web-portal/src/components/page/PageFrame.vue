<template>
  <div class="sfp-page" v-loading="loading">
    <div v-if="badge" class="page-badge">{{ badge }}</div>
    <section v-if="!hideHero" class="hero-panel page-hero">
      <div class="hero-copy">
        <h2>{{ title }}</h2>
        <div v-if="subtitle" class="page-subtitle">{{ subtitle }}</div>
      </div>
      <div class="hero-actions">
        <slot name="actions" />
      </div>
    </section>
    <slot />
    <footer v-if="$slots.legend || legend" class="page-legend">
      <slot name="legend">
        <span>{{ legend }}</span>
      </slot>
    </footer>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  badge: { type: String, default: '' },
  legend: { type: String, default: '' },
  hideHero: { type: Boolean, default: false },
  loading: { type: Boolean, default: false }
})
</script>
