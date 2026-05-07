<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <aside class="topology-legend">
    <h3 class="font-semibold mb-2">{{ t('topology.legend.title') }}</h3>
    <ul class="space-y-1 text-sm">
      <li>{{ t('topology.legend.items.powerFlow') }}</li>
      <li>{{ t('topology.legend.items.status') }}</li>
      <li>{{ t('topology.legend.items.interlock') }}</li>
    </ul>
  </aside>
</template>

<style scoped>
.topology-legend {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}
</style>
