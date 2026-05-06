<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { useI18n } from 'vue-i18n'
import { useResourceAlias } from '@/features/overview/composables/useResourceAlias'
import SelectedResourceInfoPanel from './SelectedResourceInfoPanel.vue'
import ControlPanel from './ControlPanel.vue'
import LoadUsagePanel from './LoadUsagePanel.vue'

const dashboardStore = useDashboardStore()
const { selectedResource } = storeToRefs(dashboardStore)
const { t } = useI18n()
const { hasPendingChanges, commitDraft } = useResourceAlias()

const showLoadUsage = computed(() => selectedResource.value?.resource_type === 'LOAD')
</script>

<template>
  <section class="integrated-panel">
    <div class="section-wrap">
      <h4 class="section-title">{{ t('selectedResource.sections.summary') }}</h4>
      <SelectedResourceInfoPanel />
    </div>

    <div class="section-wrap">
      <h4 class="section-title">{{ t('selectedResource.sections.control') }}</h4>
      <ControlPanel />
    </div>

    <div v-if="showLoadUsage" class="section-wrap">
      <h4 class="section-title">{{ t('selectedResource.sections.loadUsage') }}</h4>
      <LoadUsagePanel :top-only="true" />
    </div>

    <div class="save-wrap">
      <button type="button" class="save-btn" :disabled="!hasPendingChanges" @click="commitDraft">
        {{ t('selectedResource.alias.saveAll') }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.integrated-panel {
  @apply space-y-3;
}

.section-wrap {
  @apply space-y-1;
}

.section-title {
  @apply text-xs font-semibold text-slate-300;
}

.save-wrap {
  @apply flex justify-end;
}

.save-btn {
  @apply rounded border border-cyan-500 bg-cyan-600/10 px-3 py-1.5 text-xs font-semibold text-cyan-200 disabled:opacity-40;
}
</style>
