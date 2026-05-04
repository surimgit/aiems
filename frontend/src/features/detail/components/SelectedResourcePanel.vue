<script setup lang="ts">
import type { ResourceInfo } from '@/types/common'

defineProps<{
  resource: ResourceInfo | null
}>()
</script>

<template>
  <section class="panel-card">
    <h3 class="title">선택 설비 상세</h3>
    <div v-if="resource" class="content">{{ resource.resource_id }} / {{ resource.status ?? 'UNKNOWN' }}</div>
    <div v-else class="content">선택된 설비가 없습니다.</div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-2;
}

.content {
  @apply text-sm text-slate-300;
}
</style>
