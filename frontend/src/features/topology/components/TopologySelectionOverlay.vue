<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  selectedResourceId?: string | null
}>()

const { t } = useI18n()
</script>

<template>
  <div v-if="selectedResourceId" class="selection-overlay">
    {{ t('topology.selectionOverlay.selectedItem') }}: {{ selectedResourceId }}
  </div>
</template>

<style scoped>
.selection-overlay {
  @apply absolute bottom-3 left-3 rounded border border-cyan-400 bg-slate-900/90 px-3 py-2 text-cyan-200;
}
</style>
