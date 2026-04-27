<script setup lang="ts">
import type { DashboardLayoutMode, DashboardLayoutPreset } from '../layoutPresets'

defineProps<{
  mode: DashboardLayoutMode
  preset: DashboardLayoutPreset
}>()
</script>

<template>
  <div class="dashboard-shell">
    <slot name="topology" />
    <slot name="selected-resource" />
    <slot name="ai-approval" />
    <slot name="alarm-summary" />
    <slot name="power-balance" />
    <slot name="command-timeline" />
    <slot name="kpi-summary" />
  </div>
</template>

<style scoped>
.dashboard-shell {
  @apply grid grid-cols-8 lg:grid-cols-12 2xl:grid-cols-24 gap-4;
}
</style>
