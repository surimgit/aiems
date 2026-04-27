<script setup lang="ts">
defineProps<{
  selectedResourceId?: string | null
}>()
</script>

<template>
  <div v-if="selectedResourceId" class="selection-overlay">
    선택 항목: {{ selectedResourceId }}
  </div>
</template>

<style scoped>
.selection-overlay {
  @apply absolute bottom-3 left-3 rounded border border-cyan-400 bg-slate-900/90 px-3 py-2 text-cyan-200;
}
</style>
