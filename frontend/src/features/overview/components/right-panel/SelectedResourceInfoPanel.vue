<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'

const dashboardStore = useDashboardStore()
const { selectedResource, selectedEss } = storeToRefs(dashboardStore)

const statusLabelMap: Record<string, string> = {
  NORMAL: '정상',
  WARNING: '경고',
  EMERGENCY: '심각',
  OFFLINE: '오프라인',
  idle: '대기',
  charging: '충전 중',
  discharging: '방전 중',
  fault: '이상'
}

const toStatusLabel = (value: string | undefined) => {
  if (!value) return '정보 없음'
  return statusLabelMap[value] ?? value
}
</script>

<template>
  <div class="panel-content">
    <template v-if="selectedResource">
      <p class="title">{{ selectedResource.name || selectedResource.resource_id }}</p>
      <dl class="grid grid-cols-2 gap-2 text-xs text-slate-300">
        <dt>장비 ID</dt><dd>{{ selectedResource.resource_id }}</dd>
        <dt>장비 유형</dt><dd>{{ selectedResource.resource_type }}</dd>
        <dt>상태</dt><dd>{{ toStatusLabel(selectedResource.status) }}</dd>
        <dt>통신 상태</dt><dd>{{ selectedResource.comms_health ?? '정보 없음' }}</dd>
        <dt>현재 전력</dt><dd>{{ selectedResource.telemetry?.p_kw ?? '-' }} kW</dd>
        <dt>전압</dt><dd>{{ selectedResource.telemetry?.v_volt ?? '-' }} V</dd>
        <dt v-if="selectedEss">SOC</dt><dd v-if="selectedEss">{{ selectedEss.soc }}%</dd>
        <dt v-if="selectedEss">용량</dt><dd v-if="selectedEss">{{ selectedEss.capacity_kwh }} kWh</dd>
      </dl>
    </template>
    <p v-else class="text-sm text-slate-400">토폴로지에서 장비 노드를 선택하세요.</p>
  </div>
</template>

<style scoped>
.panel-content {
  @apply rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-300;
}

.title {
  @apply mb-3 text-sm font-semibold text-slate-100;
}
</style>
