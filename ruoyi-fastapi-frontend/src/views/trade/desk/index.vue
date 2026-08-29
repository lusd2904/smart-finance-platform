<template>
  <div />
</template>
<script setup name="TradeDeskIndex">
const router = useRouter()
const route = useRoute()
router.replace({ path: '/trade/terminal', query: route.query })
</script>
