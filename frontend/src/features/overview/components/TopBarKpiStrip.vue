<script setup lang="ts">
import type { PowerSummary } from '@/types/common'
import type { RightPanelMode } from '../types'

defineProps<{
  powerSummary: PowerSummary | null
  activeAlarmCount: number
  currentMode: RightPanelMode | null
  panelOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-mode', mode: RightPanelMode): void
}>()

const toggleMode = (mode: RightPanelMode) => {
  emit('toggle-mode', mode)
}
</script>

<template>
  <section class="topbar-kpi-strip">
    <div class="left-area">
      <h1 class="title">AI EMS Dashboard</h1>
      <p class="subtitle">Energy Management System</p>
    </div>

    <div class="right-area">
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'alarm' }"
        data-testid="icon-alarm"
        @click="toggleMode('alarm')"
      >
        알림 <span v-if="activeAlarmCount > 0" class="badge">{{ activeAlarmCount }}</span>
      </button>
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'recent-command' }"
        data-testid="icon-recent"
        @click="toggleMode('recent-command')"
      >
        최근 명령
      </button>
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'country-language' }"
        data-testid="icon-country"
        @click="toggleMode('country-language')"
      >
        국가/언어
      </button>
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'control' }"
        data-testid="icon-settings"
        @click="toggleMode('control')"
      >
        설정
      </button>
    </div>
  </section>
</template>

<style scoped>
.topbar-kpi-strip {
  @apply flex items-center justify-between gap-3 rounded border border-slate-700 bg-slate-900/80 p-3;
}

.left-area {
  @apply min-w-0;
}

.title {
  @apply text-2xl font-semibold text-slate-100;
}

.subtitle {
  @apply text-sm text-slate-300;
}

.right-area {
  @apply flex flex-wrap items-center justify-end gap-2;
}

.icon-btn {
  @apply rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors outline-none;
}

.icon-btn.active {
  @apply border-cyan-400 text-cyan-300;
}

.icon-btn:focus,
.icon-btn:focus-visible {
  outline: none;
  box-shadow: none;
}

.badge {
  @apply ml-1 inline-flex min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs text-white;
}
</style>
