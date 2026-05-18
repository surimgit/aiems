<script setup lang="ts">
import type { PowerSummary } from '@/types/common'
import type { RightPanelMode } from '../types'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

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
      <h1 class="title">{{ t('topbar.title') }}</h1>
      <p class="subtitle">{{ t('topbar.subtitle') }}</p>
    </div>

    <div class="right-area">
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'alarm' }"
        data-testid="icon-alarm"
        @click="toggleMode('alarm')"
      >
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 4a6 6 0 0 0-6 6v3.2l-1.5 2.6A1 1 0 0 0 5.37 17h13.26a1 1 0 0 0 .87-1.5L18 13.2V10a6 6 0 0 0-6-6Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M10 19a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
        <span>{{ t('topbar.alarm') }}</span>
        <span v-if="activeAlarmCount > 0" class="badge">{{ activeAlarmCount }}</span>
      </button>
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'recent-command' }"
        data-testid="icon-recent"
        @click="toggleMode('recent-command')"
      >
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 7h8M4 17h8M16 7h4M16 17h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          <circle cx="14" cy="7" r="2" stroke="currentColor" stroke-width="1.8"/>
          <circle cx="10" cy="17" r="2" stroke="currentColor" stroke-width="1.8"/>
        </svg>
        <span>{{ t('topbar.recent') }}</span>
      </button>
      <button
        type="button"
        class="icon-btn"
        :class="{ active: panelOpen && currentMode === 'settings' }"
        data-testid="icon-settings"
        @click="toggleMode('settings')"
      >
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" stroke="currentColor" stroke-width="1.8"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 .99-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 .99 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51.99H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51.99V15Z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>{{ t('topbar.settings') }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.topbar-kpi-strip {
  @apply flex min-h-[72px] items-center justify-between gap-3 rounded border border-slate-700 bg-slate-900/80 p-3;
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
  @apply flex flex-nowrap items-center justify-end gap-2 overflow-x-auto;
}

.icon-btn {
  @apply inline-flex items-center gap-1.5 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors outline-none;
}

.btn-icon {
  @apply h-4 w-4 shrink-0;
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
