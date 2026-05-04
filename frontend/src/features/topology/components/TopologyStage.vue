<script setup lang="ts">
import type { TopologyData } from '@/types/common'

defineProps<{
  topology: TopologyData | null
}>()

const emit = defineEmits<{
  (e: 'select-node', nodeId: string): void
  (e: 'select-line', lineId: string): void
}>()
</script>

<template>
  <section class="topology-stage">
    <div class="map-background" />
    <svg class="overlay" viewBox="0 0 1200 700" role="img" aria-label="Topology overlay">
      <slot name="svg" />
    </svg>
    <div class="overlay-ui">
      <slot name="overlay" />
    </div>
    <button class="sr-only" @click="emit('select-node', 'sample-node')">Select node</button>
  </section>
</template>

<style scoped>
.topology-stage {
  @apply relative h-full min-h-0 rounded border border-slate-700 overflow-hidden;
}

.map-background {
  @apply absolute inset-0 bg-slate-900;
  background-image: radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.2), transparent 30%);
}

.overlay {
  @apply relative z-10 w-full h-full;
}

.overlay-ui {
  @apply pointer-events-none absolute left-3 top-3 z-20;
}

.overlay-ui :deep(*) {
  @apply pointer-events-auto;
}
</style>
