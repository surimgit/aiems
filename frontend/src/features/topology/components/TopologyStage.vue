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
      <slot />
    </svg>
    <button class="sr-only" @click="emit('select-node', 'sample-node')">Select node</button>
  </section>
</template>

<style scoped>
.topology-stage {
  @apply relative rounded border border-slate-700 overflow-hidden min-h-[420px];
}

.map-background {
  @apply absolute inset-0 bg-slate-900;
  background-image: radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.2), transparent 30%);
}

.overlay {
  @apply relative z-10 w-full h-full;
}
</style>
