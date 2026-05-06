<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import SelectedResourceInfoPanel from './SelectedResourceInfoPanel.vue'
import ControlPanel from './ControlPanel.vue'
import LoadUsagePanel from './LoadUsagePanel.vue'

const dashboardStore = useDashboardStore()
const { selectedResource } = storeToRefs(dashboardStore)

const showLoadUsage = computed(() => selectedResource.value?.resource_type === 'LOAD')
</script>

<template>
  <section class="integrated-panel">
    <div class="section-wrap">
      <h4 class="section-title">선택 장비 요약</h4>
      <SelectedResourceInfoPanel />
    </div>

    <div class="section-wrap">
      <h4 class="section-title">설비 제어</h4>
      <ControlPanel />
    </div>

    <div v-if="showLoadUsage" class="section-wrap">
      <h4 class="section-title">소비처 사용 현황</h4>
      <LoadUsagePanel :top-only="true" />
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
</style>
