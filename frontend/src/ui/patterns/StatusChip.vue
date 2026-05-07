<script setup lang="ts">
defineProps<{
  label: string
  tone?: 'normal' | 'warning' | 'critical'
}>()
</script>

<template>
  <span class="status-chip"><slot>{{ label }}</slot></span>
</template>

<style scoped>
.status-chip {
  @apply inline-flex items-center rounded px-2 py-1 text-xs border border-slate-600 text-slate-200;
}
</style>
