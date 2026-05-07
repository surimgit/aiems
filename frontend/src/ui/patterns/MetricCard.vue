<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
}>()
</script>

<template>
  <article class="metric-card">
    <p class="label">{{ label }}</p>
    <p class="value">{{ value }}</p>
  </article>
</template>

<style scoped>
.metric-card {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3;
}

.label {
  @apply text-xs text-slate-400;
}

.value {
  @apply mt-1 text-lg text-slate-100;
}
</style>
