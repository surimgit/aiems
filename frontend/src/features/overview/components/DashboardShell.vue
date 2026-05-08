<script setup lang="ts">
import type { DashboardLayoutMode, DashboardLayoutPreset } from '../layoutPresets'

const props = withDefaults(defineProps<{
  mode?: DashboardLayoutMode
  preset?: DashboardLayoutPreset
  panelOpen?: boolean
  mapExpanded?: boolean
}>(), {
  mode: 'laptop',
  panelOpen: false,
  mapExpanded: false
})
</script>

<template>
  <section class="dashboard-shell" :class="[`mode-${props.mode}`, { 'panel-open': props.panelOpen, 'map-expanded': props.mapExpanded }]">
    <div class="main-area" :class="{ 'main-area-expanded': props.mapExpanded }">
      <slot name="topbar" />

      <div class="topology-area">
        <slot name="topology" />
      </div>

      <div v-if="!props.mapExpanded" class="bottom-area">
        <div class="bottom-item">
          <slot name="power-balance" />
        </div>
        <div class="bottom-item">
          <slot name="kpi-summary" />
        </div>
        <div class="bottom-item">
          <slot name="ai-performance" />
        </div>
      </div>
    </div>

    <aside v-if="props.panelOpen" class="right-panel-area">
      <slot name="right-panel" />
    </aside>
  </section>
</template>

<style scoped>
.dashboard-shell {
  @apply grid h-full min-h-0 grid-cols-1 gap-5;
}

.main-area {
  @apply grid min-h-0 grid-cols-1 gap-5;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.main-area-expanded {
  grid-template-rows: auto minmax(0, 1fr);
}

.topology-area {
  @apply min-h-0 overflow-hidden;
}

.bottom-area {
  @apply grid h-full min-h-0 grid-cols-3 gap-3;
}

.bottom-item {
  @apply h-full min-h-0 min-w-0;
}

.bottom-item > :deep(*) {
  @apply h-full min-h-0;
}

.right-panel-area {
  @apply min-h-0 overflow-auto;
}

.mode-tablet.panel-open .right-panel-area {
  @apply fixed inset-y-0 right-0 z-50 w-[88vw] max-w-[420px] border-l border-slate-700 bg-slate-950 p-4 shadow-2xl;
}

.mode-laptop.panel-open {
  @apply lg:grid-cols-[minmax(0,1fr)_380px];
}

.mode-wall.panel-open {
  @apply 2xl:grid-cols-[minmax(0,1fr)_460px];
}
</style>
