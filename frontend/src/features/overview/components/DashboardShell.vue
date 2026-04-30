<script setup lang="ts">
import type { DashboardLayoutMode, DashboardLayoutPreset } from '../layoutPresets'

defineProps<{
  mode?: DashboardLayoutMode
  preset?: DashboardLayoutPreset
  panelOpen?: boolean
}>()
</script>

<template>
  <section class="dashboard-shell" :class="{ 'panel-open': panelOpen }">
    <div class="main-area">
      <slot name="topbar" />

      <div class="topology-area">
        <slot name="topology" />
      </div>

      <div class="bottom-area">
        <slot name="power-balance" />
        <slot name="kpi-summary" />
        <slot name="ai-performance" />
      </div>
    </div>

    <aside v-if="panelOpen" class="right-panel-area">
      <slot name="right-panel" />
    </aside>
  </section>
</template>

<style scoped>
.dashboard-shell {
  @apply grid grid-cols-1 gap-4;
}

.main-area {
  @apply grid grid-cols-1 gap-4;
}

.topology-area {
  @apply min-h-[420px];
}

.bottom-area {
  @apply grid grid-cols-1 gap-4 xl:grid-cols-3;
}

.dashboard-shell.panel-open {
  @apply lg:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_420px];
}

.right-panel-area {
  @apply min-h-[420px];
}
</style>
